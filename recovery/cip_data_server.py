#!/usr/bin/env python3
"""CIP Data Streaming Server for Micro 820 PLC.

Connects to PLC via EtherNet/IP (CIP, port 44818) using pycomm3.
Exposes REST API (port 8080) and WebSocket (port 8765) for live tag data.

Usage:
    python recovery/cip_data_server.py [--host 169.254.47.96] [--poll-ms 500]
"""

import argparse
import asyncio
import json
import logging
import signal
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from threading import Thread, Lock
from typing import Any, Optional

try:
    from pycomm3 import LogixDriver
except ImportError:
    print("ERROR: pycomm3 not installed. Run: pip install pycomm3")
    sys.exit(1)

try:
    import websockets
    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("cip_data_server")

# ---------------------------------------------------------------------------
# PLC Connection
# ---------------------------------------------------------------------------

@dataclass
class PLCState:
    host: str = "169.254.47.96"
    connected: bool = False
    tag_list: list = field(default_factory=list)
    tag_values: dict = field(default_factory=dict)
    plc_info: dict = field(default_factory=dict)
    last_read: Optional[str] = None
    read_count: int = 0
    error_count: int = 0
    last_error: Optional[str] = None
    lock: Lock = field(default_factory=Lock)


def _get(obj, key, default=None):
    """Get attribute from dict or object."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def connect_plc(state: PLCState) -> Optional[LogixDriver]:
    """Connect to PLC and discover tags."""
    try:
        log.info(f"Connecting to PLC at {state.host}:44818 via CIP...")
        plc = LogixDriver(state.host)
        plc.open()

        # Get PLC info (may be dict or object depending on pycomm3 version)
        info = plc.get_plc_info()
        rev = _get(info, "revision", {})
        state.plc_info = {
            "vendor": _get(info, "vendor", "Rockwell"),
            "product_type": _get(info, "product_type", "Unknown"),
            "product_name": _get(info, "product_name", "Micro820"),
            "serial": _get(info, "serial", _get(info, "serial_number", "Unknown")),
            "revision": f"{_get(rev, 'major', '?')}.{_get(rev, 'minor', '?')}" if isinstance(rev, dict) else str(rev),
        }
        log.info(f"PLC info: {state.plc_info.get('product_name')} serial={state.plc_info.get('serial')}")

        # Discover tags (may be list of dicts or objects)
        tags = plc.get_tag_list()
        state.tag_list = [
            {
                "tag_name": _get(t, "tag_name"),
                "data_type": str(_get(t, "data_type", "?")),
                "dim": _get(t, "dim", 0),
            }
            for t in tags
        ]
        log.info(f"Discovered {len(state.tag_list)} tags: {[t['tag_name'] for t in state.tag_list[:20]]}")

        state.connected = True
        return plc

    except Exception as e:
        state.connected = False
        state.last_error = str(e)
        log.error(f"Connection failed: {e}")
        return None


def read_all_tags(plc: LogixDriver, state: PLCState) -> dict:
    """Read all discovered tags."""
    if not state.tag_list:
        return {}

    tag_names = [t["tag_name"] for t in state.tag_list]
    try:
        if len(tag_names) == 1:
            result = plc.read(tag_names[0])
            results = [result]
        else:
            results = plc.read(*tag_names)

        values = {}
        for tag_name, resp in zip(tag_names, results):
            if resp.error is None:
                val = resp.value
                if isinstance(val, float):
                    val = round(val, 3)
                values[tag_name] = val
            else:
                values[tag_name] = f"ERROR:{resp.error}"

        return values

    except Exception as e:
        log.error(f"Tag read failed: {e}")
        state.error_count += 1
        state.last_error = str(e)
        return {}


# ---------------------------------------------------------------------------
# Polling Loop
# ---------------------------------------------------------------------------

def poll_loop(plc: LogixDriver, state: PLCState, interval_s: float, json_path: Optional[Path]):
    """Continuous polling loop (runs in thread)."""
    log.info(f"Polling every {interval_s*1000:.0f}ms...")
    while state.connected:
        try:
            values = read_all_tags(plc, state)
            now = datetime.now(timezone.utc).isoformat()

            with state.lock:
                state.tag_values = values
                state.last_read = now
                state.read_count += 1

            # Write JSON snapshot
            if json_path and values:
                snapshot = {
                    "host": state.host,
                    "timestamp": now,
                    "read_count": state.read_count,
                    "tags": values,
                }
                json_path.write_text(json.dumps(snapshot, indent=2, default=str))

            if state.read_count % 20 == 1:
                log.info(f"Poll #{state.read_count}: {len(values)} tags read")

        except Exception as e:
            log.error(f"Poll error: {e}")
            state.error_count += 1
            state.last_error = str(e)
            # Try reconnect
            state.connected = False
            break

        time.sleep(interval_s)

    log.warning("Poll loop exited")


# ---------------------------------------------------------------------------
# REST API (stdlib http.server)
# ---------------------------------------------------------------------------

class APIHandler(BaseHTTPRequestHandler):
    state: PLCState = None  # Set by factory

    def do_GET(self):
        if self.path == "/api/data" or self.path == "/":
            self._json_response(self._build_data())
        elif self.path == "/api/tags":
            self._json_response({"tags": self.state.tag_list})
        elif self.path == "/api/info":
            self._json_response(self.state.plc_info)
        elif self.path == "/health":
            self._json_response({
                "status": "ok" if self.state.connected else "disconnected",
                "host": self.state.host,
                "connected": self.state.connected,
                "read_count": self.state.read_count,
                "error_count": self.state.error_count,
            })
        else:
            self.send_error(404)

    def _build_data(self) -> dict:
        with self.state.lock:
            return {
                "host": self.state.host,
                "connected": self.state.connected,
                "timestamp": self.state.last_read,
                "read_count": self.state.read_count,
                "error_count": self.state.error_count,
                "last_error": self.state.last_error,
                "tags": dict(self.state.tag_values),
                "plc_info": self.state.plc_info,
            }

    def _json_response(self, data: dict, status: int = 200):
        body = json.dumps(data, indent=2, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass  # Suppress request logs


def start_http(state: PLCState, port: int = 8080):
    handler = type("H", (APIHandler,), {"state": state})
    server = HTTPServer(("0.0.0.0", port), handler)
    log.info(f"REST API listening on http://0.0.0.0:{port}")
    log.info(f"  GET /api/data  — current tag values")
    log.info(f"  GET /api/tags  — tag list")
    log.info(f"  GET /api/info  — PLC info")
    log.info(f"  GET /health    — health check")
    Thread(target=server.serve_forever, daemon=True).start()
    return server


# ---------------------------------------------------------------------------
# WebSocket Server
# ---------------------------------------------------------------------------

async def ws_handler(websocket, state: PLCState, interval_s: float):
    """Stream tag data to WebSocket clients."""
    log.info(f"WebSocket client connected from {websocket.remote_address}")
    try:
        while state.connected:
            with state.lock:
                data = {
                    "host": state.host,
                    "connected": state.connected,
                    "timestamp": state.last_read,
                    "tags": dict(state.tag_values),
                }
            await websocket.send(json.dumps(data, default=str))
            await asyncio.sleep(interval_s)
    except websockets.exceptions.ConnectionClosed:
        log.info("WebSocket client disconnected")


async def start_ws(state: PLCState, port: int = 8765, interval_s: float = 0.5):
    if not HAS_WEBSOCKETS:
        log.warning("websockets not installed — WebSocket server disabled. pip install websockets")
        return

    async def handler(ws):
        await ws_handler(ws, state, interval_s)

    server = await websockets.serve(handler, "0.0.0.0", port)
    log.info(f"WebSocket streaming on ws://0.0.0.0:{port}")
    return server


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="CIP Data Streaming Server")
    parser.add_argument("--host", default="169.254.47.96", help="PLC IP address")
    parser.add_argument("--poll-ms", type=int, default=500, help="Poll interval in ms")
    parser.add_argument("--http-port", type=int, default=8080, help="REST API port")
    parser.add_argument("--ws-port", type=int, default=8765, help="WebSocket port")
    parser.add_argument("--json-file", default="recovery/plc_live.json", help="JSON snapshot path")
    parser.add_argument("--no-ws", action="store_true", help="Disable WebSocket server")
    args = parser.parse_args()

    state = PLCState(host=args.host)
    interval_s = args.poll_ms / 1000.0
    json_path = Path(args.json_file)
    json_path.parent.mkdir(parents=True, exist_ok=True)

    # Connect to PLC
    plc = connect_plc(state)
    if not plc:
        log.error("Cannot connect to PLC. Is it online?")
        log.info(f"  Try: ping {args.host}")
        log.info(f"  Try: python recovery/probe_plc.py {args.host}")
        sys.exit(1)

    # Start REST API
    http_server = start_http(state, args.http_port)

    # Start polling in background thread
    poll_thread = Thread(target=poll_loop, args=(plc, state, interval_s, json_path), daemon=True)
    poll_thread.start()

    # Start WebSocket server (async)
    if not args.no_ws and HAS_WEBSOCKETS:
        loop = asyncio.new_event_loop()

        async def run_ws():
            ws_server = await start_ws(state, args.ws_port, interval_s)
            if ws_server:
                await asyncio.Future()  # Run forever

        ws_thread = Thread(target=lambda: loop.run_until_complete(run_ws()), daemon=True)
        ws_thread.start()
    elif not args.no_ws:
        log.warning("Install websockets for live streaming: pip install websockets")

    log.info("=" * 60)
    log.info(f"CIP Data Server running — PLC at {args.host}")
    log.info(f"  REST:      http://localhost:{args.http_port}/api/data")
    log.info(f"  WebSocket: ws://localhost:{args.ws_port}")
    log.info(f"  JSON file: {json_path}")
    log.info(f"  Tags:      {len(state.tag_list)}")
    log.info("=" * 60)

    # Block until Ctrl+C
    try:
        while True:
            time.sleep(1)
            if not state.connected:
                log.warning("Connection lost. Attempting reconnect...")
                plc = connect_plc(state)
                if plc:
                    poll_thread = Thread(
                        target=poll_loop, args=(plc, state, interval_s, json_path), daemon=True
                    )
                    poll_thread.start()
                else:
                    time.sleep(5)
    except KeyboardInterrupt:
        log.info("Shutting down...")
        state.connected = False
        http_server.shutdown()
        if plc:
            try:
                plc.close()
            except Exception:
                pass


if __name__ == "__main__":
    main()
