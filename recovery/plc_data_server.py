#!/usr/bin/env python3
"""Full PLC Data Streaming Server — Modbus TCP (primary) + CIP fallback.

Connects to Micro 820 PLC using Modbus TCP (port 502) with automatic fallback
to CIP/EtherNet/IP (port 44818) if Modbus is unavailable.

Exposes:
  - REST API on port 8080
  - WebSocket on port 8765
  - JSON file output at recovery/plc_live.json

Register map sourced from config/factoryio.yaml.

Usage:
    python recovery/plc_data_server.py [--host 192.168.1.100] [--poll-ms 200]
    python recovery/plc_data_server.py --host 169.254.47.96 --cip-only
"""

import argparse
import asyncio
import json
import logging
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from threading import Thread, Lock
from typing import Any, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("plc_data_server")

# ---------------------------------------------------------------------------
# Optional imports
# ---------------------------------------------------------------------------

try:
    from pymodbus.client import ModbusTcpClient
    HAS_MODBUS = True
except ImportError:
    HAS_MODBUS = False

try:
    from pycomm3 import LogixDriver
    HAS_CIP = True
except ImportError:
    HAS_CIP = False

try:
    import websockets
    HAS_WS = True
except ImportError:
    HAS_WS = False

# ---------------------------------------------------------------------------
# Register Map (from config/factoryio.yaml)
# ---------------------------------------------------------------------------

COIL_MAP = {
    0: "motor_running",
    1: "motor_stopped",
    2: "fault_alarm",
    3: "conveyor_running",
    4: "sensor_1_active",
    5: "sensor_2_active",
    6: "e_stop_active",
}

REGISTER_MAP = {
    100: "motor_speed",
    101: "motor_current",
    102: "temperature",
    103: "pressure",
    104: "conveyor_speed",
    105: "error_code",
}

SCALE_FACTORS = {
    "motor_current": 0.1,
    "temperature": 0.1,
}

ERROR_CODES = {
    0: "OK",
    1: "Overload",
    2: "Overheat",
    3: "Jam",
    4: "Sensor Fault",
    5: "Comms Fault",
}

# Alternative coil map matching plc_connection.py (From A to B scene)
ALT_COIL_MAP = {
    0: "Conveyor",
    1: "Emitter",
    2: "SensorStart",
    3: "SensorEnd",
    4: "RunCommand",
    7: "DI_00",
    8: "DI_01",
    9: "DI_02",
    10: "DI_03",
    11: "DI_04",
    12: "DI_05",
    13: "DI_06",
    14: "DI_07",
    15: "DO_00",
    16: "DO_01",
    17: "DO_02",
}

ALT_REGISTER_MAP = {
    100: "ItemCount",
    101: "Reserved_101",
    102: "Reserved_102",
    103: "Reserved_103",
    104: "Reserved_104",
    105: "Reserved_105",
}


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

@dataclass
class ServerState:
    host: str = "192.168.1.100"
    mode: str = "auto"  # auto | modbus | cip
    connected: bool = False
    protocol: str = "none"  # modbus | cip | none
    coil_map: dict = field(default_factory=lambda: dict(COIL_MAP))
    register_map: dict = field(default_factory=lambda: dict(REGISTER_MAP))
    tag_values: dict = field(default_factory=dict)
    coils: dict = field(default_factory=dict)
    registers: dict = field(default_factory=dict)
    plc_info: dict = field(default_factory=dict)
    cip_tags: list = field(default_factory=list)
    last_read: Optional[str] = None
    read_count: int = 0
    error_count: int = 0
    last_error: Optional[str] = None
    lock: Lock = field(default_factory=Lock)


# ---------------------------------------------------------------------------
# Modbus Connection
# ---------------------------------------------------------------------------

def connect_modbus(state: ServerState) -> Optional[ModbusTcpClient]:
    if not HAS_MODBUS:
        log.warning("pymodbus not installed — Modbus unavailable. pip install pymodbus")
        return None

    try:
        log.info(f"Connecting via Modbus TCP to {state.host}:502...")
        client = ModbusTcpClient(state.host, port=502, timeout=3)
        if client.connect():
            log.info("Modbus TCP connected")
            state.connected = True
            state.protocol = "modbus"
            state.plc_info["protocol"] = "Modbus TCP"
            return client
        else:
            log.warning("Modbus TCP connection refused (port 502 likely closed)")
            return None
    except Exception as e:
        log.warning(f"Modbus connection failed: {e}")
        return None


def read_modbus(client: ModbusTcpClient, state: ServerState) -> bool:
    """Read coils and registers via Modbus."""
    try:
        # Read coils 0-17
        max_coil = max(max(state.coil_map.keys()), 17)
        coil_result = client.read_coils(0, max_coil + 1)
        if coil_result.isError():
            raise Exception(f"Coil read error: {coil_result}")

        coils = {}
        for addr, name in state.coil_map.items():
            if addr < len(coil_result.bits):
                coils[name] = bool(coil_result.bits[addr])

        # Read holding registers 100-105
        reg_start = min(state.register_map.keys())
        reg_count = max(state.register_map.keys()) - reg_start + 1
        reg_result = client.read_holding_registers(reg_start, reg_count)
        if reg_result.isError():
            raise Exception(f"Register read error: {reg_result}")

        registers = {}
        for addr, name in state.register_map.items():
            idx = addr - reg_start
            if idx < len(reg_result.registers):
                raw = reg_result.registers[idx]
                scale = SCALE_FACTORS.get(name, 1)
                val = round(raw * scale, 3) if scale != 1 else raw
                registers[name] = val

        # Decode error code
        if "error_code" in registers:
            registers["error_text"] = ERROR_CODES.get(registers["error_code"], "Unknown")

        with state.lock:
            state.coils = coils
            state.registers = registers
            state.tag_values = {**coils, **registers}
            state.last_read = datetime.now(timezone.utc).isoformat()
            state.read_count += 1

        return True

    except Exception as e:
        state.error_count += 1
        state.last_error = str(e)
        log.error(f"Modbus read error: {e}")
        return False


# ---------------------------------------------------------------------------
# CIP Connection (fallback)
# ---------------------------------------------------------------------------

def _get(obj, key, default=None):
    """Get attribute from dict or object."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def connect_cip(state: ServerState) -> Optional["LogixDriver"]:
    if not HAS_CIP:
        log.warning("pycomm3 not installed — CIP unavailable. pip install pycomm3")
        return None

    try:
        log.info(f"Connecting via CIP to {state.host}:44818...")
        plc = LogixDriver(state.host)
        plc.open()

        info = plc.get_plc_info()
        rev = _get(info, "revision", {})
        state.plc_info = {
            "protocol": "CIP/EtherNet/IP",
            "product_name": _get(info, "product_name", "Micro820"),
            "serial": _get(info, "serial", _get(info, "serial_number", "Unknown")),
            "revision": f"{_get(rev, 'major', '?')}.{_get(rev, 'minor', '?')}" if isinstance(rev, dict) else str(rev),
        }

        tags = plc.get_tag_list()
        state.cip_tags = [
            {"tag_name": _get(t, "tag_name"), "data_type": str(_get(t, "data_type", "?"))}
            for t in tags
        ]
        log.info(f"CIP connected — {len(state.cip_tags)} tags: {[t['tag_name'] for t in state.cip_tags[:15]]}")

        state.connected = True
        state.protocol = "cip"
        return plc

    except Exception as e:
        log.warning(f"CIP connection failed: {e}")
        return None


def read_cip(plc: "LogixDriver", state: ServerState) -> bool:
    """Read all tags via CIP."""
    if not state.cip_tags:
        return False

    tag_names = [_get(t, "tag_name") for t in state.cip_tags]
    try:
        if len(tag_names) == 1:
            results = [plc.read(tag_names[0])]
        else:
            results = plc.read(*tag_names)

        values = {}
        for name, resp in zip(tag_names, results):
            if resp.error is None:
                val = resp.value
                if isinstance(val, float):
                    val = round(val, 3)
                values[name] = val
            else:
                values[name] = f"ERROR:{resp.error}"

        with state.lock:
            state.tag_values = values
            state.last_read = datetime.now(timezone.utc).isoformat()
            state.read_count += 1

        return True

    except Exception as e:
        state.error_count += 1
        state.last_error = str(e)
        log.error(f"CIP read error: {e}")
        return False


# ---------------------------------------------------------------------------
# Unified Connect
# ---------------------------------------------------------------------------

def connect(state: ServerState):
    """Connect using best available protocol."""
    if state.mode in ("auto", "modbus"):
        client = connect_modbus(state)
        if client:
            return ("modbus", client)

    if state.mode in ("auto", "cip"):
        plc = connect_cip(state)
        if plc:
            return ("cip", plc)

    return ("none", None)


# ---------------------------------------------------------------------------
# Polling
# ---------------------------------------------------------------------------

def poll_loop(protocol: str, client: Any, state: ServerState, interval_s: float, json_path: Optional[Path]):
    log.info(f"Polling via {protocol} every {interval_s*1000:.0f}ms...")

    while state.connected:
        try:
            if protocol == "modbus":
                ok = read_modbus(client, state)
            elif protocol == "cip":
                ok = read_cip(client, state)
            else:
                break

            if not ok:
                state.error_count += 1
                if state.error_count > 10:
                    log.error("Too many errors, stopping poll")
                    state.connected = False
                    break

            # JSON snapshot
            if json_path:
                with state.lock:
                    snapshot = {
                        "host": state.host,
                        "protocol": state.protocol,
                        "connected": state.connected,
                        "timestamp": state.last_read,
                        "read_count": state.read_count,
                        "tags": dict(state.tag_values),
                    }
                    if state.protocol == "modbus":
                        snapshot["coils"] = dict(state.coils)
                        snapshot["registers"] = dict(state.registers)
                json_path.write_text(json.dumps(snapshot, indent=2, default=str))

            if state.read_count % 50 == 1:
                log.info(f"Poll #{state.read_count} ({protocol}): {len(state.tag_values)} values")

        except Exception as e:
            log.error(f"Poll error: {e}")
            state.error_count += 1
            state.last_error = str(e)

        time.sleep(interval_s)

    log.warning("Poll loop exited")


# ---------------------------------------------------------------------------
# REST API
# ---------------------------------------------------------------------------

class APIHandler(BaseHTTPRequestHandler):
    state: ServerState = None

    def do_GET(self):
        routes = {
            "/": self._data,
            "/api/data": self._data,
            "/api/tags": self._tags,
            "/api/coils": self._coils,
            "/api/registers": self._registers,
            "/api/info": self._info,
            "/health": self._health,
        }
        handler = routes.get(self.path)
        if handler:
            self._json(handler())
        else:
            self.send_error(404)

    def _data(self):
        with self.state.lock:
            return {
                "host": self.state.host,
                "protocol": self.state.protocol,
                "connected": self.state.connected,
                "timestamp": self.state.last_read,
                "read_count": self.state.read_count,
                "error_count": self.state.error_count,
                "tags": dict(self.state.tag_values),
                "coils": dict(self.state.coils),
                "registers": dict(self.state.registers),
            }

    def _tags(self):
        if self.state.protocol == "cip":
            return {"protocol": "cip", "tags": self.state.cip_tags}
        return {
            "protocol": "modbus",
            "coil_map": {str(k): v for k, v in self.state.coil_map.items()},
            "register_map": {str(k): v for k, v in self.state.register_map.items()},
        }

    def _coils(self):
        with self.state.lock:
            return {"coils": dict(self.state.coils), "timestamp": self.state.last_read}

    def _registers(self):
        with self.state.lock:
            return {"registers": dict(self.state.registers), "timestamp": self.state.last_read}

    def _info(self):
        return self.state.plc_info

    def _health(self):
        return {
            "status": "ok" if self.state.connected else "disconnected",
            "host": self.state.host,
            "protocol": self.state.protocol,
            "connected": self.state.connected,
            "read_count": self.state.read_count,
            "error_count": self.state.error_count,
        }

    def _json(self, data, status=200):
        body = json.dumps(data, indent=2, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass


def start_http(state: ServerState, port: int):
    handler = type("H", (APIHandler,), {"state": state})
    server = HTTPServer(("0.0.0.0", port), handler)
    log.info(f"REST API on http://0.0.0.0:{port}")
    log.info(f"  /api/data      — all tag values")
    log.info(f"  /api/coils     — coil states")
    log.info(f"  /api/registers — register values")
    log.info(f"  /api/tags      — tag/register map")
    log.info(f"  /api/info      — PLC info")
    log.info(f"  /health        — health check")
    Thread(target=server.serve_forever, daemon=True).start()
    return server


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------

async def ws_handler(websocket, state: ServerState, interval_s: float):
    log.info(f"WS client: {websocket.remote_address}")
    try:
        while state.connected:
            with state.lock:
                msg = {
                    "host": state.host,
                    "protocol": state.protocol,
                    "connected": state.connected,
                    "timestamp": state.last_read,
                    "tags": dict(state.tag_values),
                    "coils": dict(state.coils),
                    "registers": dict(state.registers),
                }
            await websocket.send(json.dumps(msg, default=str))
            await asyncio.sleep(interval_s)
    except Exception:
        log.info("WS client disconnected")


async def start_ws(state: ServerState, port: int, interval_s: float):
    if not HAS_WS:
        log.warning("websockets not installed — WS disabled. pip install websockets")
        return None
    server = await websockets.serve(lambda ws: ws_handler(ws, state, interval_s), "0.0.0.0", port)
    log.info(f"WebSocket on ws://0.0.0.0:{port}")
    return server


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="PLC Data Streaming Server")
    parser.add_argument("--host", default="192.168.1.100", help="PLC IP")
    parser.add_argument("--poll-ms", type=int, default=200, help="Poll interval ms")
    parser.add_argument("--http-port", type=int, default=8080, help="REST port")
    parser.add_argument("--ws-port", type=int, default=8765, help="WebSocket port")
    parser.add_argument("--json-file", default="recovery/plc_live.json", help="JSON output")
    parser.add_argument("--cip-only", action="store_true", help="Skip Modbus, use CIP only")
    parser.add_argument("--modbus-only", action="store_true", help="Skip CIP, use Modbus only")
    parser.add_argument("--alt-map", action="store_true",
                        help="Use alternative coil map (From A to B scene)")
    parser.add_argument("--no-ws", action="store_true", help="Disable WebSocket")
    args = parser.parse_args()

    state = ServerState(host=args.host)

    if args.cip_only:
        state.mode = "cip"
    elif args.modbus_only:
        state.mode = "modbus"

    if args.alt_map:
        state.coil_map = dict(ALT_COIL_MAP)
        state.register_map = dict(ALT_REGISTER_MAP)
        log.info("Using alternative coil/register map (From A to B scene)")

    interval_s = args.poll_ms / 1000.0
    json_path = Path(args.json_file)
    json_path.parent.mkdir(parents=True, exist_ok=True)

    # Connect
    protocol, client = connect(state)
    if not client:
        log.error("Cannot connect to PLC via any protocol")
        if not HAS_MODBUS:
            log.info("  Install pymodbus:  pip install pymodbus")
        if not HAS_CIP:
            log.info("  Install pycomm3:   pip install pycomm3")
        log.info(f"  Verify PLC is reachable: ping {args.host}")
        sys.exit(1)

    # Start HTTP
    http_server = start_http(state, args.http_port)

    # Start polling
    poll_thread = Thread(target=poll_loop, args=(protocol, client, state, interval_s, json_path), daemon=True)
    poll_thread.start()

    # Start WebSocket
    if not args.no_ws and HAS_WS:
        loop = asyncio.new_event_loop()
        async def run():
            await start_ws(state, args.ws_port, interval_s)
            await asyncio.Future()
        Thread(target=lambda: loop.run_until_complete(run()), daemon=True).start()

    log.info("=" * 60)
    log.info(f"PLC Data Server — {state.host} via {protocol.upper()}")
    log.info(f"  REST:      http://localhost:{args.http_port}/api/data")
    if not args.no_ws and HAS_WS:
        log.info(f"  WebSocket: ws://localhost:{args.ws_port}")
    log.info(f"  JSON:      {json_path}")
    log.info(f"  Poll:      {args.poll_ms}ms")
    log.info("=" * 60)

    # Main loop with reconnect
    try:
        while True:
            time.sleep(1)
            if not state.connected:
                log.warning("Connection lost. Reconnecting in 5s...")
                time.sleep(5)
                protocol, client = connect(state)
                if client:
                    poll_thread = Thread(
                        target=poll_loop,
                        args=(protocol, client, state, interval_s, json_path),
                        daemon=True,
                    )
                    poll_thread.start()
    except KeyboardInterrupt:
        log.info("Shutting down...")
        state.connected = False
        http_server.shutdown()
        if protocol == "modbus" and client:
            client.close()
        elif protocol == "cip" and client:
            try:
                client.close()
            except Exception:
                pass


if __name__ == "__main__":
    main()
