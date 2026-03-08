"""Scene Manager — Factory I/O scene lifecycle, I/O discovery, Modbus R/W.

Handles:
- I/O discovery via Factory I/O web API (localhost:7410)
- Official PLC program loading + I/O map parsing
- Modbus TCP reads/writes via pymodbus
- Sim control (start/stop/reset via web API tags)
- Stability detection (wait for tags to settle)
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml

from services.learner.knowledge_store import IOPoint
from services.learner.safety import pre_write_check

logger = logging.getLogger("factorylm.learner.scene_manager")

REPO_ROOT = Path(__file__).parent.parent.parent

# Factory I/O web API (local sim)
FIO_API_BASE = os.getenv("FIO_API_BASE", "http://localhost:7410")

# Modbus TCP (Factory I/O Modbus server or real PLC)
MODBUS_HOST = os.getenv("MODBUS_HOST", "127.0.0.1")
MODBUS_PORT = int(os.getenv("MODBUS_PORT", "502"))

# Known scene configs
FACTORYIO_CONFIG = REPO_ROOT / "config" / "factoryio.yaml"
SCENES_DIR = REPO_ROOT / "services" / "plc-modbus" / "scenes"
RECOVERY_DIR = REPO_ROOT / "recovery"


# ---------------------------------------------------------------------------
# Factory I/O Web API (reuses pattern from tools/fio_event_monitor.py)
# ---------------------------------------------------------------------------

def get_fio_tags() -> list[dict]:
    """Fetch all tags from Factory I/O web API."""
    req = urllib.request.Request(f"{FIO_API_BASE}/api/tags")
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read().decode())


def get_fio_tag_map() -> dict[str, dict]:
    """Fetch tags and return as {name: tag_dict} map."""
    tags = get_fio_tags()
    return {t["name"]: t for t in tags}


def set_fio_tag(tag_name: str, value) -> bool:
    """Write a single tag via Factory I/O web API."""
    tags = get_fio_tags()
    target = next((t for t in tags if t["name"] == tag_name), None)
    if not target:
        logger.error("Tag not found: %s", tag_name)
        return False

    payload = json.dumps({"value": value}).encode()
    req = urllib.request.Request(
        f"{FIO_API_BASE}/api/tag",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="PUT",
    )
    # Factory I/O expects the tag ID in the URL
    req = urllib.request.Request(
        f"{FIO_API_BASE}/api/tags/{target['id']}",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="PUT",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except Exception as exc:
        logger.error("Failed to set tag %s: %s", tag_name, exc)
        return False


# ---------------------------------------------------------------------------
# Sim control via Factory I/O system tags
# ---------------------------------------------------------------------------

def is_sim_running() -> bool:
    """Check if Factory I/O simulation is running."""
    try:
        tags = get_fio_tag_map()
        running_tag = tags.get("FACTORY I/O (Running)")
        if running_tag:
            return bool(running_tag.get("value"))
    except Exception:
        pass
    return False


def start_simulation() -> bool:
    """Start the Factory I/O simulation."""
    return set_fio_tag("FACTORY I/O (Running)", True)


def stop_simulation() -> bool:
    """Stop the Factory I/O simulation."""
    return set_fio_tag("FACTORY I/O (Running)", False)


def reset_simulation() -> bool:
    """Reset the Factory I/O simulation."""
    return set_fio_tag("FACTORY I/O (Reset)", True)


# ---------------------------------------------------------------------------
# Modbus TCP client (reuses pattern from modbus_client.py)
# ---------------------------------------------------------------------------

_modbus_client = None


def _get_modbus():
    """Lazy-init Modbus TCP client."""
    global _modbus_client
    if _modbus_client is not None:
        return _modbus_client
    try:
        from pymodbus.client import ModbusTcpClient
        _modbus_client = ModbusTcpClient(MODBUS_HOST, port=MODBUS_PORT, timeout=3)
        if not _modbus_client.connect():
            logger.error("Modbus connect failed: %s:%s", MODBUS_HOST, MODBUS_PORT)
            _modbus_client = None
        return _modbus_client
    except ImportError:
        logger.error("pymodbus not installed — pip install pymodbus")
        return None


def read_coils(address: int = 0, count: int = 16) -> Optional[list[bool]]:
    """Read coils from Modbus server."""
    client = _get_modbus()
    if not client:
        return None
    result = client.read_coils(address=address, count=count, slave=1)
    if result.isError():
        logger.error("Coil read error at %d: %s", address, result)
        return None
    return [bool(b) for b in result.bits[:count]]


def read_discrete_inputs(address: int = 0, count: int = 16) -> Optional[list[bool]]:
    """Read discrete inputs from Modbus server."""
    client = _get_modbus()
    if not client:
        return None
    result = client.read_discrete_inputs(address=address, count=count, slave=1)
    if result.isError():
        logger.error("DI read error at %d: %s", address, result)
        return None
    return [bool(b) for b in result.bits[:count]]


def read_holding_registers(address: int = 0, count: int = 10) -> Optional[list[int]]:
    """Read holding registers from Modbus server."""
    client = _get_modbus()
    if not client:
        return None
    result = client.read_holding_registers(address=address, count=count, slave=1)
    if result.isError():
        logger.error("Register read error at %d: %s", address, result)
        return None
    return list(result.registers)


def write_coil(address: int, value: bool, tag_name: str = "",
               current_tags: Optional[dict] = None) -> bool:
    """Write a single coil with safety check."""
    safe, reason = pre_write_check(tag_name or f"coil_{address}", current_tags)
    if not safe:
        logger.warning("Write blocked: %s", reason)
        return False

    client = _get_modbus()
    if not client:
        return False
    result = client.write_coil(address=address, value=value, slave=1)
    if result.isError():
        logger.error("Coil write error at %d: %s", address, result)
        return False
    return True


def write_register(address: int, value: int, tag_name: str = "",
                   current_tags: Optional[dict] = None) -> bool:
    """Write a single holding register with safety check."""
    safe, reason = pre_write_check(tag_name or f"reg_{address}", current_tags)
    if not safe:
        logger.warning("Write blocked: %s", reason)
        return False

    client = _get_modbus()
    if not client:
        return False
    result = client.write_register(address=address, value=value, slave=1)
    if result.isError():
        logger.error("Register write error at %d: %s", address, result)
        return False
    return True


def clear_all_coils(count: int = 16) -> bool:
    """Reset all coils to False (safe state)."""
    client = _get_modbus()
    if not client:
        return False
    for addr in range(count):
        client.write_coil(addr, False, slave=1)
    return True


# ---------------------------------------------------------------------------
# Tag snapshot (combined Modbus + web API)
# ---------------------------------------------------------------------------

def read_all_tags(io_map: Optional[dict] = None) -> dict:
    """Read all tags and return a named dict.

    If io_map is provided (from parse_program_io), uses Modbus with friendly names.
    Otherwise falls back to Factory I/O web API.
    """
    if io_map:
        return _read_tags_modbus(io_map)
    return _read_tags_web_api()


def _read_tags_web_api() -> dict:
    """Read all tags via Factory I/O web API."""
    try:
        tags = get_fio_tags()
        return {t["name"]: t["value"] for t in tags}
    except Exception as exc:
        logger.error("Web API read failed: %s", exc)
        return {}


def _read_tags_modbus(io_map: dict) -> dict:
    """Read tags via Modbus using a parsed I/O map."""
    result = {}

    # Group by io_type
    dis = {name: addr for name, (addr, io_type) in io_map.items()
           if io_type == "discrete_input"}
    coils = {name: addr for name, (addr, io_type) in io_map.items()
             if io_type == "coil"}
    regs = {name: addr for name, (addr, io_type) in io_map.items()
            if io_type == "register"}

    if dis:
        max_addr = max(dis.values())
        bits = read_discrete_inputs(0, max_addr + 1)
        if bits:
            for name, addr in dis.items():
                result[name] = bits[addr] if addr < len(bits) else False

    if coils:
        max_addr = max(coils.values())
        bits = read_coils(0, max_addr + 1)
        if bits:
            for name, addr in coils.items():
                result[name] = bits[addr] if addr < len(bits) else False

    if regs:
        max_addr = max(regs.values())
        vals = read_holding_registers(0, max_addr + 1)
        if vals:
            for name, addr in regs.items():
                result[name] = vals[addr] if addr < len(vals) else 0

    return result


# ---------------------------------------------------------------------------
# PLC Program Loading + I/O Parsing
# ---------------------------------------------------------------------------

def load_scene_config(scene_name: str) -> Optional[dict]:
    """Load scene configuration from config/factoryio.yaml or scene directory.

    Returns the raw YAML dict for the scene, or None if not found.
    """
    # Try config/factoryio.yaml first
    if FACTORYIO_CONFIG.exists():
        with open(FACTORYIO_CONFIG) as f:
            config = yaml.safe_load(f)
        fio = config.get("factoryio", {})
        # Currently factoryio.yaml is single-scene; check if it matches
        if scene_name.lower() in fio.get("scene", "").lower():
            return fio

    # Try scene-specific YAML in scenes directory
    for pattern in [f"{scene_name}.yaml", f"{scene_name.lower().replace(' ', '_')}.yaml"]:
        path = SCENES_DIR / pattern
        if path.exists():
            with open(path) as f:
                return yaml.safe_load(f)

    return None


def parse_program_io(scene_name: str, config: Optional[dict] = None) -> list[IOPoint]:
    """Parse a scene's I/O map into IOPoint objects.

    Sources (in priority order):
    1. Provided config dict
    2. config/factoryio.yaml
    3. Factory I/O web API tag discovery
    """
    if config is None:
        config = load_scene_config(scene_name)

    if config:
        return _parse_io_from_config(scene_name, config)

    # Fallback: discover from Factory I/O web API
    return _parse_io_from_web_api(scene_name)


def _parse_io_from_config(scene_name: str, config: dict) -> list[IOPoint]:
    """Parse I/O points from a YAML config dict."""
    points = []

    # Discrete inputs
    dis = config.get("discrete_inputs", {})
    for addr, name in dis.items():
        comment = ""
        if isinstance(name, dict):
            comment = name.get("description", "")
            name = name.get("name", f"di_{addr}")
        points.append(IOPoint(
            tag_name=str(name),
            address=int(addr),
            io_type="discrete_input",
            data_type="BOOL",
            description=comment,
            scene_name=scene_name,
        ))

    # Coils
    coils = config.get("coils", {})
    for addr, name in coils.items():
        comment = ""
        if isinstance(name, dict):
            comment = name.get("description", "")
            name = name.get("name", f"coil_{addr}")
        points.append(IOPoint(
            tag_name=str(name),
            address=int(addr),
            io_type="coil",
            data_type="BOOL",
            description=comment,
            scene_name=scene_name,
        ))

    # Registers
    regs = config.get("registers", {})
    for addr, name in regs.items():
        comment = ""
        if isinstance(name, dict):
            comment = name.get("description", "")
            name = name.get("name", f"reg_{addr}")
        points.append(IOPoint(
            tag_name=str(name),
            address=int(addr),
            io_type="register",
            data_type="INT",
            description=comment,
            scene_name=scene_name,
        ))

    return points


def _parse_io_from_web_api(scene_name: str) -> list[IOPoint]:
    """Discover I/O points from Factory I/O web API."""
    try:
        tags = get_fio_tags()
    except Exception as exc:
        logger.error("Cannot discover I/O from web API: %s", exc)
        return []

    points = []
    for t in tags:
        # Skip system tags
        if t["name"].startswith("FACTORY I/O"):
            continue

        io_type = "discrete_input" if t["kind"] == "Input" else "coil"
        data_type = "BOOL" if t["type"] in ("Bool", "bool") else "INT"
        if t["type"] in ("Float", "float", "Real", "real"):
            data_type = "REAL"

        points.append(IOPoint(
            tag_name=t["name"],
            address=t.get("address", 0),
            io_type=io_type,
            data_type=data_type,
            description="",  # Web API doesn't provide descriptions
            scene_name=scene_name,
        ))

    return points


def build_io_lookup(io_points: list[IOPoint]) -> dict:
    """Build a lookup dict: {tag_name: (address, io_type)} for Modbus reads."""
    return {pt.tag_name: (pt.address, pt.io_type) for pt in io_points}


# ---------------------------------------------------------------------------
# Stability detection
# ---------------------------------------------------------------------------

def wait_for_stable(io_map: Optional[dict] = None,
                    timeout_s: float = 5.0,
                    settle_count: int = 3,
                    poll_interval: float = 0.3) -> dict:
    """Poll tags until no changes for `settle_count` consecutive reads.

    Returns the final stable tag snapshot.
    """
    prev = read_all_tags(io_map)
    stable_reads = 0
    deadline = time.time() + timeout_s

    while time.time() < deadline:
        time.sleep(poll_interval)
        current = read_all_tags(io_map)

        if current == prev:
            stable_reads += 1
            if stable_reads >= settle_count:
                logger.debug("Tags stable after %d reads", stable_reads)
                return current
        else:
            stable_reads = 0
            prev = current

    logger.warning("Stability timeout after %.1fs", timeout_s)
    return prev


# ---------------------------------------------------------------------------
# Tag delta computation
# ---------------------------------------------------------------------------

def compute_tag_delta(before: dict, after: dict) -> dict:
    """Compute which tags changed between two snapshots.

    Returns: {tag_name: {"old": old_val, "new": new_val}}
    """
    delta = {}
    all_keys = set(before.keys()) | set(after.keys())
    for key in all_keys:
        old = before.get(key)
        new = after.get(key)
        if old != new:
            delta[key] = {"old": old, "new": new}
    return delta


# ---------------------------------------------------------------------------
# Screenshot capture (reuses pattern from cookoff/capture_fio.py)
# ---------------------------------------------------------------------------

SCREENSHOT_DIR = REPO_ROOT / "data" / "learner" / "screenshots"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


def capture_screenshot(label: str = "screenshot", monitor_index: int = 1) -> Optional[str]:
    """Capture a screenshot and save to data/learner/screenshots/."""
    try:
        import mss
        import mss.tools
    except ImportError:
        logger.error("mss not installed — pip install mss")
        return None

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    filename = f"{label}_{timestamp}.png"
    output_path = SCREENSHOT_DIR / filename

    with mss.mss() as sct:
        monitor = sct.monitors[monitor_index]
        screenshot = sct.grab(monitor)
        png_bytes = mss.tools.to_png(screenshot.rgb, screenshot.size)

    output_path.write_bytes(png_bytes)
    logger.info("Screenshot saved: %s", output_path)
    return str(output_path)


# ---------------------------------------------------------------------------
# Scene reset (full clean lifecycle)
# ---------------------------------------------------------------------------

def reset_to_clean(scene_name: str, coil_count: int = 16) -> bool:
    """Full clean reset: stop sim, clear coils, reset, start.

    Note: Loading a different scene requires GUI automation (not implemented here).
    This handles the Modbus/API-level reset for the currently loaded scene.
    """
    logger.info("Resetting scene '%s' to clean state", scene_name)

    # Stop simulation
    stop_simulation()
    time.sleep(0.5)

    # Clear all coils
    clear_all_coils(coil_count)
    time.sleep(0.5)

    # Reset simulation
    reset_simulation()
    time.sleep(1.0)

    # Start simulation
    start_simulation()
    time.sleep(1.0)

    running = is_sim_running()
    if running:
        logger.info("Scene '%s' reset and running", scene_name)
    else:
        logger.warning("Scene '%s' may not be running after reset", scene_name)

    return running
