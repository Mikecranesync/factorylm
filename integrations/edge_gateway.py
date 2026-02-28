"""
Edge Gateway Integration — Modbus TCP client wrapper
=====================================================
Connects to an Allen-Bradley Micro 820 PLC via Modbus TCP.
Used by VPS Celery workers to poll PLC registers remotely
through the tailnet.

Micro 820 Modbus address map:
  Coils 0-6:    program vars (motor_running, motor_stopped, fault_alarm, etc.)
  Coils 7-14:   DI (physical inputs)
  Coils 15-17:  DO (physical outputs)
  Holding Regs 100-105: motor_speed, motor_current, temperature,
                        pressure, conveyor_speed, error_code
"""

import os
import time
import logging
from typing import Any, Dict, Optional

from pymodbus.client import ModbusTcpClient

logger = logging.getLogger(__name__)

DEFAULT_IP = os.getenv("EDGE_GATEWAY_IP", "192.168.1.100")
DEFAULT_PORT = 502
TIMEOUT = 3  # seconds


def connect_to_edge(ip: str) -> Dict[str, Any]:
    """Test connectivity to the edge gateway PLC.

    Returns dict with status "connected" or "error".
    """
    client = None
    try:
        client = ModbusTcpClient(ip, port=DEFAULT_PORT, timeout=TIMEOUT)
        start = time.time()
        connected = client.connect()
        latency_ms = round((time.time() - start) * 1000, 2)

        if connected:
            logger.info("Connected to edge gateway at %s (%.1f ms)", ip, latency_ms)
            return {"status": "connected", "latency_ms": latency_ms}
        else:
            logger.warning("Failed to connect to edge gateway at %s", ip)
            return {"status": "error", "error": f"Connection refused by {ip}:{DEFAULT_PORT}"}
    except Exception as exc:
        logger.error("Edge gateway connection error: %s", exc)
        return {"status": "error", "error": str(exc)}
    finally:
        if client is not None:
            client.close()


def read_plc_registers(
    register_start: int,
    count: int,
    slave_id: int = 1,
    ip: Optional[str] = None,
) -> Dict[str, Any]:
    """Read holding registers from the PLC.

    Returns dict with status, values list, and latency_ms on success,
    or status "error" with error message on failure.
    """
    target_ip = ip or DEFAULT_IP
    client = None
    try:
        client = ModbusTcpClient(target_ip, port=DEFAULT_PORT, timeout=TIMEOUT)
        if not client.connect():
            return {"status": "error", "error": f"Cannot connect to {target_ip}:{DEFAULT_PORT}"}

        start = time.time()
        result = client.read_holding_registers(register_start, count=count, device_id=slave_id)
        latency_ms = round((time.time() - start) * 1000, 2)

        if result.isError():
            logger.warning("Modbus read error at register %d: %s", register_start, result)
            return {"status": "error", "error": str(result)}

        logger.debug("Read registers %d-%d: %s (%.1f ms)",
                      register_start, register_start + count - 1,
                      result.registers, latency_ms)
        return {"status": "success", "values": list(result.registers), "latency_ms": latency_ms}
    except Exception as exc:
        logger.error("PLC register read failed: %s", exc)
        return {"status": "error", "error": str(exc)}
    finally:
        if client is not None:
            client.close()


def health_check(ip: str) -> Dict[str, Any]:
    """Full health check: connectivity test + trial register read.

    Returns dict with top-level status, connectivity sub-dict,
    and modbus_test sub-dict.
    """
    # 1. Connectivity test
    conn = connect_to_edge(ip)
    if conn.get("status") != "connected":
        return {
            "status": "unhealthy",
            "connectivity": {"status": "error", "error": conn.get("error", "unknown")},
            "modbus_test": {"status": "skipped"},
        }

    # 2. Trial read — holding register 100 (motor_speed)
    modbus = read_plc_registers(100, 1, slave_id=1, ip=ip)

    if modbus.get("status") == "success":
        return {
            "status": "healthy",
            "connectivity": {"latency_ms": conn.get("latency_ms", 0)},
            "modbus_test": {"status": "success", "latency_ms": modbus.get("latency_ms", 0)},
        }
    else:
        return {
            "status": "degraded",
            "connectivity": {"latency_ms": conn.get("latency_ms", 0)},
            "modbus_test": {"status": "error", "error": modbus.get("error", "unknown")},
        }
