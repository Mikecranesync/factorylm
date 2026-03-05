"""
Factory I/O Sorting Controller — Python Soft PLC.

Drives the "Sorting by Height (Basic)" scene via Factory I/O's Web API.
No CODESYS or PLC hardware required.

Architecture:
    Factory I/O (scene running, Web API enabled on :7410)
        | HTTP REST (id-based, lowercase fields)
    This script (reads sensors, runs state machine, writes actuators)
        | Optional
    /api/plc/live endpoint for Cosmos diagnosis

API contract (Factory I/O Web API — EmbedIO server):
    GET  /api/tags          -> [{name, id, address, type, kind, value, isForced, ...}]
    GET  /api/tag/values    -> [{id, value}]
    PUT  /api/tag/values    <- [{id, value}]  (output tags only)
    PUT  /api/tag/values-force   <- [{id, value}]
    PUT  /api/tag/values-release <- ["id"]

Usage:
    python sim/sorting_controller.py                    # Run controller
    python sim/sorting_controller.py --discover         # Dump all tags
    python sim/sorting_controller.py --api-url http://host:7410
    python sim/sorting_controller.py --dry-run          # Read-only mode
"""

import argparse
import datetime
import json
import logging
import os
import signal
import sys
import time
from enum import IntEnum
from pathlib import Path
from threading import Event, Lock, Thread

_repo_root = str(Path(__file__).resolve().parent.parent)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

import httpx

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("sorting_controller")
# Suppress noisy httpx request logging
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


# ---------------------------------------------------------------------------
# State machine (modeled after recovery/Micro820_v1.9.st CASE pattern)
# ---------------------------------------------------------------------------
class State(IntEnum):
    INIT = 0           # All outputs OFF, stop light ON, waiting for Start
    RUNNING = 1        # Entry conveyor ON, green light ON, waiting for box
    SETTLING = 2       # Conveyor stopped, waiting 3 scans for sensors to settle
    SORTING_LEFT = 3   # Transfer left active, waiting for exit sensor
    SORTING_RIGHT = 4  # Transfer right active, waiting for exit sensor
    STOPPED = 5        # All outputs OFF, yellow light ON, waiting for Reset
    ESTOP = 6          # All outputs OFF immediately, red light ON


STATE_NAMES = {s: s.name for s in State}


# ---------------------------------------------------------------------------
# Factory I/O Web API client (id-based, lowercase fields)
# ---------------------------------------------------------------------------
class FactoryIOClient:
    """HTTP client for Factory I/O Web API (port 7410).

    Factory I/O uses UUIDs (id) to identify tags, not names.
    On init, we fetch /api/tags to build name<->id lookup tables.
    All read/write operations use IDs internally.
    """

    def __init__(self, base_url: str = "http://localhost:7410", timeout: float = 2.0):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client(timeout=timeout)
        self._connected = False
        # Lookup tables built from /api/tags
        self._name_to_id: dict[str, str] = {}      # "Conveyor entry" -> "uuid" (prefers Output)
        self._id_to_name: dict[str, str] = {}      # "uuid" -> "Conveyor entry"
        self._tag_meta: dict[str, dict] = {}        # name -> full tag dict
        self._output_names: set[str] = set()
        self._input_name_to_id: dict[str, str] = {}  # "Start" -> input UUID
        self._kind_by_id: dict[str, str] = {}         # UUID -> "Input"/"Output"

    def check_connection(self) -> bool:
        """Connect and build name<->id lookup from /api/tags."""
        try:
            r = self.client.get(f"{self.base_url}/api/tags")
            r.raise_for_status()
            tags = r.json()
            self._name_to_id.clear()
            self._id_to_name.clear()
            self._tag_meta.clear()
            self._output_names.clear()
            self._input_name_to_id.clear()
            self._kind_by_id.clear()
            collisions = []
            input_count = 0
            output_count = 0
            for t in tags:
                name = t["name"]
                tid = t["id"]
                kind = t.get("kind", "")
                # Track kind for every UUID
                self._kind_by_id[tid] = kind
                # Map ALL UUIDs to names (not just the winner)
                self._id_to_name[tid] = name
                if kind == "Input":
                    input_count += 1
                    self._input_name_to_id[name] = tid
                if kind == "Output":
                    output_count += 1
                    self._output_names.add(name)
                # _name_to_id prefers Output (for writes via _name_id)
                if name in self._name_to_id:
                    if kind == "Output":
                        collisions.append(name)
                        self._name_to_id[name] = tid
                    # else: keep existing (Output already stored, or first-seen)
                else:
                    self._name_to_id[name] = tid
                self._tag_meta[name] = t
            self._connected = True
            for c in collisions:
                logger.warning("Tag name collision: '%s' has both Input and Output — reads will prefer Input", c)
            logger.info("Loaded %d tags (%d inputs, %d outputs)", len(self._name_to_id), input_count, output_count)
            return True
        except Exception as e:
            logger.warning("Factory I/O not reachable at %s: %s", self.base_url, e)
            self._connected = False
            return False

    @property
    def connected(self) -> bool:
        return self._connected

    def _name_id(self, name: str) -> str | None:
        tid = self._name_to_id.get(name)
        if tid is None:
            logger.warning("Unknown tag name: %s", name)
        return tid

    def get_all_tags(self) -> list[dict] | None:
        """GET /api/tags — full tag metadata."""
        try:
            r = self.client.get(f"{self.base_url}/api/tags")
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.error("Failed to get tags: %s", e)
            return None

    def read_all_values(self) -> dict | None:
        """GET /api/tag/values -> dict of tag_name: value.

        When a name has both Input and Output tags, the Input value wins.
        This ensures sensor reads are never shadowed by actuator values.
        """
        try:
            r = self.client.get(f"{self.base_url}/api/tag/values")
            r.raise_for_status()
            raw = r.json()  # [{id, value}, ...]
            result = {}
            for item in raw:
                tid = item["id"]
                name = self._id_to_name.get(tid)
                if not name:
                    continue
                kind = self._kind_by_id.get(tid, "")
                # If name already stored and current tag is NOT Input, skip —
                # Input (sensor) values always win over Output (actuator) values.
                if name in result and kind != "Input":
                    continue
                result[name] = item["value"]
            return result
        except Exception as e:
            logger.warning("Read values failed: %s", e)
            self._connected = False
            return None

    def write_tags(self, tag_values: dict) -> bool:
        """Write multiple tags by name. Only writes Output tags."""
        payload = []
        for name, value in tag_values.items():
            tid = self._name_id(name)
            if tid and name in self._output_names:
                payload.append({"id": tid, "value": value})
        if not payload:
            return True
        try:
            r = self.client.put(
                f"{self.base_url}/api/tag/values",
                json=payload,
            )
            r.raise_for_status()
            # Check for errors in response
            resp = r.json()
            for item in resp:
                if item.get("error"):
                    logger.warning("Write error: %s", item)
            return True
        except Exception as e:
            logger.warning("Write tags failed: %s", e)
            return False

    def force_tag(self, tag_name: str, value) -> bool:
        """Force a tag value (overrides scene logic)."""
        tid = self._name_id(tag_name)
        if not tid:
            return False
        try:
            r = self.client.put(
                f"{self.base_url}/api/tag/values-force",
                json=[{"id": tid, "value": value}],
            )
            r.raise_for_status()
            return True
        except Exception as e:
            logger.warning("Force %s=%s failed: %s", tag_name, value, e)
            return False

    def release_tag(self, tag_name: str) -> bool:
        """Release a forced tag (return to scene logic)."""
        tid = self._name_id(tag_name)
        if not tid:
            return False
        try:
            r = self.client.put(
                f"{self.base_url}/api/tag/values-release",
                json=[tid],
            )
            r.raise_for_status()
            return True
        except Exception as e:
            logger.warning("Release %s failed: %s", tag_name, e)
            return False


# ---------------------------------------------------------------------------
# Config loader
# ---------------------------------------------------------------------------
def load_config(path: str = "config/sorting_tags.yaml") -> dict:
    """Load tag mapping config. Returns defaults matching 'Sorting by Height (Basic)' scene."""
    defaults = {
        "api_url": "http://localhost:7410",
        "poll_interval_ms": 100,
        # Actual Factory I/O tag names for "Sorting by Height (Basic)"
        "sensors": {
            "high_sensor": "High sensor",
            "low_sensor": "Low sensor",
            "pallet_sensor": "Pallet sensor",
            "at_left_entry": "At left entry",
            "at_left_exit": "At left exit",
            "at_right_entry": "At right entry",
            "at_right_exit": "At right exit",
            "start": "Start",
            "stop": "Stop",
            "reset": "Reset",
            "emergency_stop": "Emergency stop",
            "auto": "Auto",
            "manual": "Manual",
            "loaded": "Loaded",
        },
        "actuators": {
            "entry_conveyor": "Conveyor entry",
            "left_conveyor": "Conveyor left",
            "right_conveyor": "Conveyor right",
            "transfer_left": "Transf. left",
            "transfer_right": "Transf. right",
            "load": "Load",
            "unload": "Unload",
            "emitter": "Emitter",
            "remover_left": "Remover left",
            "remover_right": "Remover right",
            "counter": "Counter",
            "start_light": "Start light",
            "stop_light": "Stop light",
            "reset_light": "Reset light",
        },
    }

    cfg_file = Path(path)
    if cfg_file.exists():
        try:
            import yaml
            with cfg_file.open("r", encoding="utf-8") as f:
                raw = yaml.safe_load(f) or {}
            fio = raw.get("factoryio", raw)
            defaults["api_url"] = fio.get("api_url", defaults["api_url"])
            defaults["poll_interval_ms"] = fio.get("poll_interval_ms", defaults["poll_interval_ms"])
            for section in ("sensors", "actuators"):
                if section in fio:
                    defaults[section].update(fio[section])
            logger.info("Config loaded from %s", cfg_file)
        except ImportError:
            logger.warning("PyYAML not installed — using defaults")
        except Exception:
            logger.exception("Config load error from %s", cfg_file)
    return defaults


# ---------------------------------------------------------------------------
# Sorting Controller
# ---------------------------------------------------------------------------
class SortingController:
    """State machine for "Sorting by Height (Basic)" via Factory I/O Web API.

    Rebuilt from official Factory I/O template logic:
    - Rising edge detection on Start/Stop/Reset (no re-trigger on held buttons)
    - E-stop and Stop use NC convention (False=engaged/pressed)
    - Height classification uses BOTH high and low sensors
    - Settling delay (3 scans) before reading height after conveyor stop
    - Sensor-based transfer completion with 15s watchdog safety net
    """

    # Settling delay: number of scans to wait after conveyor stop
    SETTLE_SCANS = 3
    # Watchdog: max scans before force-completing a transfer (15s at 100ms)
    WATCHDOG_SCANS = 150

    def __init__(self, client: FactoryIOClient, config: dict, dry_run: bool = False):
        self.fio = client
        self.cfg = config
        self.dry_run = dry_run

        self.s = config["sensors"]
        self.a = config["actuators"]

        # State
        self.state = State.INIT
        self.tags: dict = {}
        self.sorted_count = 0
        self.total_count = 0
        self.tall_count = 0
        self.short_count = 0
        self.last_sort_result = ""
        self.start_time = time.monotonic()

        # Settling / watchdog counters
        self._settle_count = 0
        self._watchdog_count = 0

        # Rising edge detection: track "active" state (True=action requested)
        # Start/Reset are NO (True=pressed), Stop is NC (True=released, invert)
        self._prev_start = False
        self._prev_stop = False   # tracks stop_active (inverted NC signal)
        self._prev_reset = False
        # Exit sensor edges for transfer completion
        self._prev_at_left_exit = False
        self._prev_at_right_exit = False

        # Thread-safe tag snapshot for diagnosis API
        self._lock = Lock()
        self._snapshot: dict = {}

    def get_snapshot(self) -> dict:
        with self._lock:
            return dict(self._snapshot)

    def _update_snapshot(self):
        with self._lock:
            self._snapshot = {
                "timestamp": datetime.datetime.now(tz=datetime.timezone.utc).isoformat(),
                "state": STATE_NAMES.get(self.state, "UNKNOWN"),
                "state_id": int(self.state),
                "sorted_count": self.sorted_count,
                "tall_count": self.tall_count,
                "short_count": self.short_count,
                "total_count": self.total_count,
                "last_sort_result": self.last_sort_result,
                "uptime_s": round(time.monotonic() - self.start_time, 1),
                "dry_run": self.dry_run,
                "tags": dict(self.tags),
                "tag_source": "factoryio_webapi",
            }

    def _read_sensors(self) -> bool:
        values = self.fio.read_all_values()
        if values is None:
            return False
        self.tags = values
        return True

    def _write(self, tag_values: dict):
        if self.dry_run:
            return
        self.fio.write_tags(tag_values)

    def _sensor(self, logical_name: str, default=False):
        tag_name = self.s.get(logical_name, logical_name)
        return self.tags.get(tag_name, default)

    def _all_outputs_off(self):
        """Kill all actuators immediately."""
        self._write({
            self.a["entry_conveyor"]: False,
            self.a["left_conveyor"]: False,
            self.a["right_conveyor"]: False,
            self.a["emitter"]: False,
            self.a["transfer_left"]: False,
            self.a["transfer_right"]: False,
            self.a["start_light"]: False,
            self.a["stop_light"]: False,
            self.a["reset_light"]: False,
        })

    def tick(self):
        """One scan cycle of the sorting state machine."""
        if not self._read_sensors():
            return

        prev_state = self.state

        # --- Button active states (normalized: True = action requested) ---
        start_active = self._sensor("start")                  # NO: True=pressed
        stop_active = not self._sensor("stop")                 # NC: True=released -> invert
        reset_active = self._sensor("reset")                   # NO: True=pressed
        estop_engaged = not self._sensor("emergency_stop")     # NC: True=safe -> invert

        # --- Rising edge detection (curr AND NOT prev) ---
        start_rising = start_active and not self._prev_start
        stop_rising = stop_active and not self._prev_stop
        reset_rising = reset_active and not self._prev_reset

        # --- Exit sensor rising edges (for transfer completion) ---
        at_left_exit = self._sensor("at_left_exit")
        at_right_exit = self._sensor("at_right_exit")
        left_exit_rising = at_left_exit and not self._prev_at_left_exit
        right_exit_rising = at_right_exit and not self._prev_at_right_exit

        # --- E-stop check: highest priority, every tick, before state logic ---
        if estop_engaged and self.state != State.ESTOP:
            self._all_outputs_off()
            self._write({self.a["stop_light"]: True})  # red indicator
            self.state = State.ESTOP
            logger.warning("E-STOP ENGAGED — all outputs OFF")

        # --- State machine ---
        elif self.state == State.INIT:
            # All outputs off, stop light on, waiting for Start
            self._write({
                self.a["entry_conveyor"]: False,
                self.a["left_conveyor"]: True,
                self.a["right_conveyor"]: True,
                self.a["emitter"]: False,
                self.a["remover_left"]: True,
                self.a["remover_right"]: True,
                self.a["transfer_left"]: False,
                self.a["transfer_right"]: False,
                self.a["start_light"]: True,
                self.a["stop_light"]: False,
                self.a["reset_light"]: False,
                self.a["counter"]: 0,
            })
            if start_rising:
                self.state = State.RUNNING
                logger.info("INIT -> RUNNING: start pressed")

        elif self.state == State.RUNNING:
            if stop_rising:
                self.state = State.STOPPED
                logger.info("RUNNING -> STOPPED: stop pressed")
            else:
                # Entry conveyor ON, waiting for box at pallet sensor
                pallet = self._sensor("pallet_sensor")
                if pallet:
                    # Box arrived — stop conveyor, begin settling
                    self._write({self.a["entry_conveyor"]: False})
                    self._settle_count = 0
                    self.state = State.SETTLING
                    logger.info("RUNNING -> SETTLING: box at pallet sensor")
                else:
                    # Keep running
                    self._write({
                        self.a["entry_conveyor"]: True,
                        self.a["left_conveyor"]: True,
                        self.a["right_conveyor"]: True,
                        self.a["emitter"]: True,
                        self.a["remover_left"]: True,
                        self.a["remover_right"]: True,
                        self.a["transfer_left"]: False,
                        self.a["transfer_right"]: False,
                        self.a["start_light"]: True,
                        self.a["stop_light"]: False,
                    })

        elif self.state == State.SETTLING:
            if stop_rising:
                self.state = State.STOPPED
                logger.info("SETTLING -> STOPPED: stop pressed")
            else:
                # Wait for sensors to settle after conveyor stop
                self._settle_count += 1
                if self._settle_count >= self.SETTLE_SCANS:
                    # Read height sensors
                    high = self._sensor("high_sensor")
                    low = self._sensor("low_sensor")
                    if high and low:
                        # TALL box -> route LEFT
                        self._write({
                            self.a["transfer_left"]: True,
                            self.a["transfer_right"]: False,
                            self.a["left_conveyor"]: True,
                        })
                        self._watchdog_count = 0
                        self.state = State.SORTING_LEFT
                        logger.info("SETTLING -> SORTING_LEFT: tall box (high=%s low=%s)", high, low)
                    elif low and not high:
                        # SHORT box -> route RIGHT
                        self._write({
                            self.a["transfer_left"]: False,
                            self.a["transfer_right"]: True,
                            self.a["right_conveyor"]: True,
                        })
                        self._watchdog_count = 0
                        self.state = State.SORTING_RIGHT
                        logger.info("SETTLING -> SORTING_RIGHT: short box (high=%s low=%s)", high, low)
                    else:
                        # Neither sensor triggered — box may have moved, go back to RUNNING
                        logger.warning("SETTLING: no height detected (high=%s low=%s) — returning to RUNNING", high, low)
                        self.state = State.RUNNING

        elif self.state == State.SORTING_LEFT:
            if stop_rising:
                self._write({self.a["transfer_left"]: False})
                self.state = State.STOPPED
                logger.info("SORTING_LEFT -> STOPPED: stop pressed")
            else:
                self._watchdog_count += 1
                if left_exit_rising:
                    # Box reached left exit — transfer complete
                    self._write({self.a["transfer_left"]: False})
                    self.tall_count += 1
                    self.sorted_count += 1
                    self.last_sort_result = "LEFT"
                    self._write({self.a["counter"]: self.sorted_count})
                    self.state = State.RUNNING
                    logger.info("Part sorted LEFT (tall) [#%d]", self.sorted_count)
                elif self._watchdog_count >= self.WATCHDOG_SCANS:
                    # Watchdog: exit sensor never fired — force-complete
                    self._write({self.a["transfer_left"]: False})
                    self.tall_count += 1
                    self.sorted_count += 1
                    self.last_sort_result = "LEFT"
                    self._write({self.a["counter"]: self.sorted_count})
                    self.state = State.RUNNING
                    logger.warning("WATCHDOG: left transfer timed out after %d scans — force-completing", self._watchdog_count)

        elif self.state == State.SORTING_RIGHT:
            if stop_rising:
                self._write({self.a["transfer_right"]: False})
                self.state = State.STOPPED
                logger.info("SORTING_RIGHT -> STOPPED: stop pressed")
            else:
                self._watchdog_count += 1
                if right_exit_rising:
                    # Box reached right exit — transfer complete
                    self._write({self.a["transfer_right"]: False})
                    self.short_count += 1
                    self.sorted_count += 1
                    self.last_sort_result = "RIGHT"
                    self._write({self.a["counter"]: self.sorted_count})
                    self.state = State.RUNNING
                    logger.info("Part sorted RIGHT (short) [#%d]", self.sorted_count)
                elif self._watchdog_count >= self.WATCHDOG_SCANS:
                    # Watchdog: exit sensor never fired — force-complete
                    self._write({self.a["transfer_right"]: False})
                    self.short_count += 1
                    self.sorted_count += 1
                    self.last_sort_result = "RIGHT"
                    self._write({self.a["counter"]: self.sorted_count})
                    self.state = State.RUNNING
                    logger.warning("WATCHDOG: right transfer timed out after %d scans — force-completing", self._watchdog_count)

        elif self.state == State.STOPPED:
            self._write({
                self.a["entry_conveyor"]: False,
                self.a["emitter"]: False,
                self.a["transfer_left"]: False,
                self.a["transfer_right"]: False,
                self.a["start_light"]: False,
                self.a["stop_light"]: True,
                self.a["reset_light"]: True,
            })
            if reset_rising:
                self.sorted_count = 0
                self.tall_count = 0
                self.short_count = 0
                self.total_count = 0
                self._write({self.a["counter"]: 0})
                self.state = State.INIT
                logger.info("STOPPED -> INIT: reset pressed (counters cleared)")

        elif self.state == State.ESTOP:
            # Hold all outputs off, red light on
            self._all_outputs_off()
            self._write({self.a["stop_light"]: True})
            # Exit: e-stop released AND reset rising edge
            if not estop_engaged and reset_rising:
                self._write({self.a["stop_light"]: False, self.a["reset_light"]: False})
                self.state = State.INIT
                logger.info("ESTOP -> INIT: e-stop released + reset pressed")

        # --- Update edge detection state (MUST be after all state logic) ---
        self._prev_start = start_active
        self._prev_stop = stop_active
        self._prev_reset = reset_active
        self._prev_at_left_exit = at_left_exit
        self._prev_at_right_exit = at_right_exit

        if self.state != prev_state:
            logger.info("State: %s -> %s", STATE_NAMES[prev_state], STATE_NAMES[self.state])

        self._update_snapshot()

    def stop(self):
        """Graceful shutdown."""
        self.state = State.STOPPED
        self._all_outputs_off()
        self._write({self.a["stop_light"]: True})
        logger.info("Controller stopped. Sorted %d parts (%d tall, %d short).",
                     self.sorted_count, self.tall_count, self.short_count)


# ---------------------------------------------------------------------------
# Optional HTTP API for diagnosis integration
# ---------------------------------------------------------------------------
def start_api_server(controller: SortingController, port: int = 8765):
    """Start a minimal HTTP server exposing /api/plc/live."""
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            if self.path in ("/api/plc/live", "/api/plc/live/"):
                snapshot = controller.get_snapshot()
                body = json.dumps(snapshot, default=str).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(body)
            elif self.path in ("/health", "/health/"):
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "ok"}).encode())
            else:
                self.send_response(404)
                self.end_headers()

    server = HTTPServer(("0.0.0.0", port), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info("API server listening on http://0.0.0.0:%d/api/plc/live", port)
    return server


# ---------------------------------------------------------------------------
# Tag discovery
# ---------------------------------------------------------------------------
def discover_tags(client: FactoryIOClient):
    """Print all Factory I/O tags with actual field names."""
    tags = client.get_all_tags()
    if tags is None:
        logger.error("Could not retrieve tags. Is Factory I/O running with Web API enabled?")
        return

    # Filter system vs scene tags
    system = [t for t in tags if t["name"].startswith("FACTORY I/O")]
    scene = [t for t in tags if not t["name"].startswith("FACTORY I/O")]

    print(f"\n{'='*70}")
    print(f"Scene Tags ({len(scene)} tags)")
    print(f"{'='*70}")
    for t in sorted(scene, key=lambda x: (x["kind"], x["name"])):
        forced = " [FORCED]" if t.get("isForced") else ""
        print(f"  {t['kind']:<8} {t['type']:<5} addr={t['address']:<4} "
              f"{t['name']:<25} = {t['value']}{forced}")
        print(f"           id={t['id']}")

    print(f"\n{'='*70}")
    print(f"System Tags ({len(system)} tags)")
    print(f"{'='*70}")
    for t in sorted(system, key=lambda x: x["name"]):
        print(f"  {t['kind']:<8} {t['name']:<30} = {t['value']}")

    # Dump values via /api/tag/values to confirm format
    print(f"\n{'='*70}")
    print("Live Values (via /api/tag/values)")
    print(f"{'='*70}")
    values = client.read_all_values()
    if values:
        for name, val in sorted(values.items()):
            print(f"  {name:<30} = {val}")
    else:
        print("  (failed to read values)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Factory I/O Sorting Controller (Python Soft PLC)")
    parser.add_argument("--api-url", default=os.getenv("FACTORYIO_URL", "http://localhost:7410"))
    parser.add_argument("--config", default="config/sorting_tags.yaml")
    parser.add_argument("--discover", action="store_true", help="Dump all tags and exit")
    parser.add_argument("--dry-run", action="store_true", help="Read-only mode")
    parser.add_argument("--interval", type=int, default=0, help="Override poll interval (ms)")
    parser.add_argument("--port", type=int, default=8765, help="API server port")
    parser.add_argument("--no-api", action="store_true", help="Disable API server")
    args = parser.parse_args()

    config = load_config(args.config)
    api_url = args.api_url or config["api_url"]
    interval_ms = args.interval or config["poll_interval_ms"]

    client = FactoryIOClient(base_url=api_url)

    if not client.check_connection():
        logger.error("Cannot connect to Factory I/O at %s", api_url)
        logger.info("Enable: press \\ in Factory I/O, type: app.web_server = True")
        sys.exit(1)

    logger.info("Connected to Factory I/O at %s", api_url)

    # Check if the scene is actually running (F5)
    all_tags = client.get_all_tags()
    if all_tags:
        running_tag = next((t for t in all_tags if t["name"] == "FACTORY I/O (Running)"), None)
        if running_tag and not running_tag.get("value"):
            logger.warning("Scene is NOT running — press F5 in Factory I/O to start the scene")

    if args.discover:
        discover_tags(client)
        return

    controller = SortingController(client, config, dry_run=args.dry_run)

    api_server = None
    if not args.no_api:
        api_server = start_api_server(controller, port=args.port)

    stop_event = Event()

    def on_signal(signum, frame):
        logger.info("Shutdown signal received")
        stop_event.set()

    signal.signal(signal.SIGINT, on_signal)
    signal.signal(signal.SIGTERM, on_signal)

    logger.info("Starting sorting controller (poll=%dms, dry_run=%s)", interval_ms, args.dry_run)
    cycle = 0
    interval_s = interval_ms / 1000.0

    while not stop_event.is_set():
        controller.tick()
        cycle += 1

        if cycle % max(1, int(10000 / interval_ms)) == 0:
            snap = controller.get_snapshot()
            logger.info(
                "Cycle %d | state=%s | sorted=%d (tall=%d short=%d) | total=%d | uptime=%.0fs",
                cycle, snap["state"], snap["sorted_count"],
                snap["tall_count"], snap["short_count"],
                snap["total_count"], snap["uptime_s"],
            )

        stop_event.wait(interval_s)

    controller.stop()
    if api_server:
        api_server.shutdown()


if __name__ == "__main__":
    main()
