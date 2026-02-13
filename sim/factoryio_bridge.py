"""
Factory I/O → Matrix API bridge.

Reads PLC tags via Modbus TCP (from Factory I/O or real PLC) and posts them
to the Matrix API for ingestion. Falls back to the built-in PLC simulator
if no Modbus connection is available.

Usage:
    # With Factory I/O running (Modbus server enabled):
    python sim/factoryio_bridge.py

    # With built-in simulator (no Factory I/O needed):
    python sim/factoryio_bridge.py --sim

    # Custom settings:
    python sim/factoryio_bridge.py --plc-host 192.168.1.100 --matrix-url http://localhost:8000
"""

import argparse
import datetime
import sys
from pathlib import Path

# Ensure repo root is on sys.path so 'sim' and 'cosmos' packages are importable
_repo_root = str(Path(__file__).resolve().parent.parent)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

import json
import logging
import os
import time

import httpx

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def read_from_modbus(host: str, port: int) -> dict | None:
    """Read tags from a Modbus TCP server (Factory I/O or real PLC)."""
    try:
        from pymodbus.client import ModbusTcpClient
    except ImportError:
        logger.error("pymodbus not installed. Install with: pip install pymodbus")
        return None

    client = ModbusTcpClient(host, port=port, timeout=3)
    if not client.connect():
        return None

    try:
        # Read coils 0-6 (program variables)
        coils_result = client.read_coils(address=0, count=7)
        if coils_result.isError():
            return None
        coils = [bool(b) for b in coils_result.bits[:7]]

        # Read holding registers 100-105
        regs_result = client.read_holding_registers(address=100, count=6)
        if regs_result.isError():
            return None
        regs = regs_result.registers

        return {
            "timestamp": datetime.datetime.now(tz=datetime.timezone.utc).isoformat(),
            "node_id": f"plc-{host}",
            "motor_running": coils[0],
            "motor_speed": regs[0],
            "motor_current": round(regs[1] / 10.0, 2),
            "temperature": round(regs[2] / 10.0, 1),
            "pressure": regs[3],
            "conveyor_running": coils[3],
            "conveyor_speed": regs[4],
            "sensor_1": coils[4],
            "sensor_2": coils[5],
            "fault_alarm": coils[2],
            "e_stop": coils[6],
            "error_code": regs[5],
            "error_message": {0:"No error",1:"Motor overload",2:"Temperature high",
                              3:"Conveyor jam",4:"Sensor failure",5:"Communication loss"}.get(regs[5], f"Error {regs[5]}"),
        }
    except Exception as e:
        logger.warning("Modbus read error: %s", e)
        return None
    finally:
        client.close()


def read_from_simulator(sim) -> dict:
    """Read tags from the built-in PLCSimulator."""
    snap = sim.tick()
    return snap.to_dict()


def post_to_matrix(matrix_url: str, tags: dict) -> bool:
    """POST tag snapshot to Matrix API."""
    try:
        resp = httpx.post(f"{matrix_url}/api/tags", json=tags, timeout=5)
        resp.raise_for_status()
        result = resp.json()
        if result.get("incident_id"):
            logger.info("🚨 Incident #%d created: %s", result["incident_id"], tags.get("error_message", ""))
        return True
    except httpx.ConnectError:
        logger.warning("Cannot reach Matrix API at %s", matrix_url)
        return False
    except Exception as e:
        logger.warning("POST failed: %s", e)
        return False


def run_bridge(
    plc_host: str = "127.0.0.1",
    plc_port: int = 502,
    matrix_url: str = "http://localhost:8000",
    interval_ms: int = 500,
    use_sim: bool = False,
) -> None:
    """Run the bridge loop."""
    sim = None
    if use_sim:
        from sim.plc_simulator import PLCSimulator
        sim = PLCSimulator(node_id="sim-factoryio", db_path="sim/bridge_tags.db")
        logger.info("Using built-in PLC simulator (no Modbus connection)")
    else:
        logger.info("Connecting to Modbus at %s:%d", plc_host, plc_port)

    logger.info("Bridge started — posting to %s every %dms", matrix_url, interval_ms)
    logger.info("Type 'jam', 'overload', 'clear', etc. to inject faults (sim mode only)")

    posted = 0
    errors = 0

    while True:
        if use_sim and sim:
            # Check stdin for fault commands (non-blocking)
            import select
            # On Windows, select doesn't work on stdin, so skip interactive in sim mode
            tags = read_from_simulator(sim)
        else:
            tags = read_from_modbus(plc_host, plc_port)

        if tags:
            if post_to_matrix(matrix_url, tags):
                posted += 1
                if posted % 20 == 0:  # Log every 10 seconds at 500ms interval
                    logger.info("Posted %d snapshots (%d errors)", posted, errors)
            else:
                errors += 1
        else:
            if not use_sim:
                logger.warning("No data from Modbus — is Factory I/O running with Modbus server enabled?")
            errors += 1

        time.sleep(interval_ms / 1000.0)


def main():
    parser = argparse.ArgumentParser(description="Factory I/O → Matrix API bridge")
    parser.add_argument("--plc-host", default=os.getenv("PLC_HOST", "127.0.0.1"), help="Modbus TCP host")
    parser.add_argument("--plc-port", type=int, default=int(os.getenv("PLC_PORT", "502")), help="Modbus TCP port")
    parser.add_argument("--matrix-url", default=os.getenv("MATRIX_URL", "http://localhost:8000"), help="Matrix API URL")
    parser.add_argument("--interval", type=int, default=500, help="Interval between reads (ms)")
    parser.add_argument("--sim", action="store_true", help="Use built-in simulator instead of Modbus")
    args = parser.parse_args()

    try:
        run_bridge(
            plc_host=args.plc_host,
            plc_port=args.plc_port,
            matrix_url=args.matrix_url,
            interval_ms=args.interval,
            use_sim=args.sim,
        )
    except KeyboardInterrupt:
        logger.info("Bridge stopped.")


if __name__ == "__main__":
    main()
