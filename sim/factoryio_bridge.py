"""
Factory I/O → Matrix API bridge.

Reads PLC tags via Modbus TCP (from Factory I/O or real PLC) and posts them
to the Matrix API for ingestion. Falls back to the built-in PLC simulator
if no Modbus connection is available.

Loads connection and tag mapping from config/factoryio.yaml.

Usage:
    python sim/factoryio_bridge.py                     # Factory I/O via Modbus
    python sim/factoryio_bridge.py --sim               # Built-in simulator
    python sim/factoryio_bridge.py --interval 200      # 200ms polling (5 Hz)
    python sim/factoryio_bridge.py --plc-host 192.168.1.100
"""

import argparse
import datetime
import json
import logging
import os
import sys
import time
from pathlib import Path

_repo_root = str(Path(__file__).resolve().parent.parent)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

import httpx

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Error codes matching services/plc-modbus
ERROR_CODES = {
    0: "No error", 1: "Motor overload", 2: "Temperature high",
    3: "Conveyor jam", 4: "Sensor failure", 5: "Communication loss",
}


def load_config(config_path: str = "config/factoryio.yaml") -> dict:
    """Load bridge config from YAML. Returns defaults if file missing."""
    defaults = {
        "host": "127.0.0.1",
        "port": 502,
        "matrix_url": "http://localhost:8000",
        "interval_ms": 500,
        "coils": {0: "motor_running", 1: "motor_stopped", 2: "fault_alarm",
                  3: "conveyor_running", 4: "sensor_1_active", 5: "sensor_2_active",
                  6: "e_stop_active"},
        "registers": {100: "motor_speed", 101: "motor_current", 102: "temperature",
                      103: "pressure", 104: "conveyor_speed", 105: "error_code"},
    }
    cfg_file = Path(config_path)
    if cfg_file.exists():
        try:
            import yaml
            with cfg_file.open("r", encoding="utf-8") as f:
                raw = yaml.safe_load(f) or {}
            fio = raw.get("factoryio", {})
            defaults["host"] = fio.get("host", defaults["host"])
            defaults["port"] = fio.get("port", defaults["port"])
            defaults["matrix_url"] = fio.get("matrix_url", defaults["matrix_url"])
            defaults["interval_ms"] = fio.get("interval_ms", defaults["interval_ms"])
            if "coils" in fio:
                defaults["coils"] = {int(k): v for k, v in fio["coils"].items()}
            if "registers" in fio:
                defaults["registers"] = {int(k): v for k, v in fio["registers"].items()}
            logger.info("Config loaded from %s", cfg_file)
        except ImportError:
            logger.warning("PyYAML not installed — using defaults")
        except Exception:
            logger.exception("Failed to load config from %s", cfg_file)
    return defaults


class ModbusReader:
    """Persistent Modbus TCP connection for high-frequency polling."""

    def __init__(self, host: str, port: int, coil_map: dict, register_map: dict):
        self.host = host
        self.port = port
        self.coil_map = coil_map
        self.register_map = register_map
        self._client = None

    def connect(self) -> bool:
        try:
            from pymodbus.client import ModbusTcpClient
        except ImportError:
            logger.error("pymodbus not installed. Run: pip install pymodbus")
            return False

        self._client = ModbusTcpClient(self.host, port=self.port, timeout=3)
        if self._client.connect():
            logger.info("Modbus connected to %s:%d", self.host, self.port)
            return True
        logger.warning("Modbus connection failed to %s:%d", self.host, self.port)
        self._client = None
        return False

    def disconnect(self):
        if self._client:
            self._client.close()
            self._client = None

    @property
    def connected(self) -> bool:
        return self._client is not None and self._client.is_socket_open()

    def read_tags(self) -> dict | None:
        """Read all mapped tags. Returns None on error."""
        if not self.connected and not self.connect():
            return None

        try:
            # Determine coil range
            coil_addrs = sorted(self.coil_map.keys())
            coil_start = coil_addrs[0]
            coil_count = coil_addrs[-1] - coil_start + 1

            coils_result = self._client.read_coils(address=coil_start, count=coil_count)
            if coils_result.isError():
                logger.warning("Coil read error")
                self.disconnect()
                return None
            coil_bits = list(coils_result.bits[:coil_count])

            # Determine register range
            reg_addrs = sorted(self.register_map.keys())
            reg_start = reg_addrs[0]
            reg_count = reg_addrs[-1] - reg_start + 1

            regs_result = self._client.read_holding_registers(address=reg_start, count=reg_count)
            if regs_result.isError():
                logger.warning("Register read error")
                self.disconnect()
                return None
            reg_values = regs_result.registers

            # Build tag dict
            tags = {
                "timestamp": datetime.datetime.now(tz=datetime.timezone.utc).isoformat(),
                "node_id": f"factoryio-{self.host}",
            }

            for addr, name in self.coil_map.items():
                idx = addr - coil_start
                tags[name] = bool(coil_bits[idx])

            for addr, name in self.register_map.items():
                idx = addr - reg_start
                raw = reg_values[idx]
                # Apply scaling for known tags
                if name == "motor_current":
                    tags[name] = round(raw / 10.0, 2)
                elif name == "temperature":
                    tags[name] = round(raw / 10.0, 1)
                else:
                    tags[name] = raw

            # Map to Matrix API field names
            result = {
                "timestamp": tags["timestamp"],
                "node_id": tags["node_id"],
                "motor_running": tags.get("motor_running", False),
                "motor_speed": tags.get("motor_speed", 0),
                "motor_current": tags.get("motor_current", 0.0),
                "temperature": tags.get("temperature", 0.0),
                "pressure": tags.get("pressure", 0),
                "conveyor_running": tags.get("conveyor_running", False),
                "conveyor_speed": tags.get("conveyor_speed", 0),
                "sensor_1": tags.get("sensor_1_active", False),
                "sensor_2": tags.get("sensor_2_active", False),
                "fault_alarm": tags.get("fault_alarm", False),
                "e_stop": tags.get("e_stop_active", False),
                "error_code": tags.get("error_code", 0),
                "error_message": ERROR_CODES.get(tags.get("error_code", 0), "Unknown"),
            }
            return result

        except Exception as e:
            logger.warning("Modbus read error: %s", e)
            self.disconnect()
            return None


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
    coil_map: dict | None = None,
    register_map: dict | None = None,
) -> None:
    """Run the bridge loop with stats tracking."""
    sim = None
    reader = None

    if use_sim:
        from sim.plc_simulator import PLCSimulator
        sim = PLCSimulator(node_id="sim-factoryio", db_path="sim/bridge_tags.db")
        logger.info("Using built-in PLC simulator (no Modbus connection)")
    else:
        reader = ModbusReader(
            plc_host, plc_port,
            coil_map or {0: "motor_running", 2: "fault_alarm", 3: "conveyor_running",
                         4: "sensor_1_active", 5: "sensor_2_active", 6: "e_stop_active"},
            register_map or {100: "motor_speed", 101: "motor_current", 102: "temperature",
                             103: "pressure", 104: "conveyor_speed", 105: "error_code"},
        )

    logger.info("Bridge started — posting to %s every %dms (%.1f Hz)",
                matrix_url, interval_ms, 1000.0 / interval_ms)

    posted = 0
    poll_errors = 0
    post_errors = 0
    start_time = time.monotonic()
    last_fault = None

    while True:
        if use_sim and sim:
            tags = sim.tick().to_dict()
        elif reader:
            tags = reader.read_tags()
        else:
            tags = None

        if tags:
            if post_to_matrix(matrix_url, tags):
                posted += 1
            else:
                post_errors += 1

            # Track fault transitions
            is_fault = tags.get("fault_alarm", False)
            if is_fault and not last_fault:
                logger.info("⚡ FAULT DETECTED: %s (error_code=%s)",
                            tags.get("error_message", "?"), tags.get("error_code", "?"))
            elif not is_fault and last_fault:
                logger.info("✅ Fault cleared")
            last_fault = is_fault
        else:
            poll_errors += 1

        # Stats every 30 seconds
        elapsed = time.monotonic() - start_time
        if posted > 0 and posted % max(1, int(30000 / interval_ms)) == 0:
            rate = posted / elapsed if elapsed > 0 else 0
            logger.info(
                "Stats: %d posted, %d poll_errors, %d post_errors, %.1f posts/sec, uptime %.0fs",
                posted, poll_errors, post_errors, rate, elapsed,
            )

        time.sleep(interval_ms / 1000.0)


def main():
    config = load_config()

    parser = argparse.ArgumentParser(description="Factory I/O → Matrix API bridge")
    parser.add_argument("--plc-host", default=os.getenv("PLC_HOST", config["host"]))
    parser.add_argument("--plc-port", type=int, default=int(os.getenv("PLC_PORT", str(config["port"]))))
    parser.add_argument("--matrix-url", default=os.getenv("MATRIX_URL", config["matrix_url"]))
    parser.add_argument("--interval", type=int, default=config["interval_ms"], help="Poll interval (ms)")
    parser.add_argument("--sim", action="store_true", help="Use built-in simulator instead of Modbus")
    args = parser.parse_args()

    try:
        run_bridge(
            plc_host=args.plc_host,
            plc_port=args.plc_port,
            matrix_url=args.matrix_url,
            interval_ms=args.interval,
            use_sim=args.sim,
            coil_map=config.get("coils"),
            register_map=config.get("registers"),
        )
    except KeyboardInterrupt:
        logger.info("Bridge stopped.")


if __name__ == "__main__":
    main()
