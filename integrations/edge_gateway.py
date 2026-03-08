"""
Edge Gateway Integration — Modbus TCP client + plc-modbus API client
=====================================================================
Connects to an Allen-Bradley Micro 820 PLC either directly via Modbus TCP
or through the plc-modbus FastAPI service.

Mode selection (env var ``EDGE_MODE``):
  - ``modbus``  — direct pymodbus TCP connection (default, for RPi / local)
  - ``api``     — HTTP calls to the plc-modbus FastAPI service (for VPS workers)

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

logger = logging.getLogger(__name__)

DEFAULT_IP = os.getenv("EDGE_GATEWAY_IP", "192.168.1.100")
DEFAULT_PORT = int(os.getenv("EDGE_GATEWAY_PORT", "502"))
TIMEOUT = int(os.getenv("EDGE_GATEWAY_TIMEOUT", "3"))
EDGE_MODE = os.getenv("EDGE_MODE", "modbus").lower()  # "modbus" or "api"
PLC_API_PORT = int(os.getenv("PLC_API_PORT", "8001"))


# ---------------------------------------------------------------------------
# Modbus TCP client with persistent connection
# ---------------------------------------------------------------------------

class EdgeGatewayClient:
    """Persistent Modbus TCP client with auto-reconnect.

    Usage::

        client = EdgeGatewayClient("192.168.1.100")
        client.connect()
        data = client.read_plc_registers(100, 6)
        # ... reuse across multiple reads ...
        client.close()
    """

    def __init__(self, ip: str = DEFAULT_IP, port: int = DEFAULT_PORT, timeout: int = TIMEOUT):
        self.ip = ip
        self.port = port
        self.timeout = timeout
        self._client = None

    def __repr__(self):
        connected = self._client is not None and self._client.connected
        return f"<EdgeGatewayClient {self.ip}:{self.port} connected={connected}>"

    def connect(self) -> Dict[str, Any]:
        """Connect (or reconnect) to the PLC. Returns status dict."""
        from pymodbus.client import ModbusTcpClient

        if self._client is not None and self._client.connected:
            return {"status": "connected", "latency_ms": 0}

        self._client = ModbusTcpClient(self.ip, port=self.port, timeout=self.timeout)
        start = time.time()
        ok = self._client.connect()
        latency_ms = round((time.time() - start) * 1000, 2)

        if ok:
            logger.info("Connected to edge gateway at %s:%d (%.1f ms)", self.ip, self.port, latency_ms)
            return {"status": "connected", "latency_ms": latency_ms}
        else:
            logger.warning("Failed to connect to edge gateway at %s:%d", self.ip, self.port)
            self._client = None
            return {"status": "error", "error": f"Connection refused by {self.ip}:{self.port}"}

    def _ensure_connected(self) -> bool:
        """Auto-reconnect if the connection dropped. Returns True if connected."""
        if self._client is not None and self._client.connected:
            return True
        result = self.connect()
        return result.get("status") == "connected"

    def read_plc_registers(
        self,
        register_start: int,
        count: int,
        slave_id: int = 1,
    ) -> Dict[str, Any]:
        """Read holding registers from the PLC."""
        if not self._ensure_connected():
            return {"status": "error", "error": f"Cannot connect to {self.ip}:{self.port}"}

        try:
            start = time.time()
            result = self._client.read_holding_registers(register_start, count=count, slave=slave_id)
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
            # Connection may be broken — clear it so next call reconnects
            self._client = None
            return {"status": "error", "error": str(exc)}

    def health_check(self) -> Dict[str, Any]:
        """Full health check: connectivity + trial register read."""
        conn = self.connect()
        if conn.get("status") != "connected":
            return {
                "status": "unhealthy",
                "connectivity": {"status": "error", "error": conn.get("error", "unknown")},
                "modbus_test": {"status": "skipped"},
            }

        modbus = self.read_plc_registers(100, 1, slave_id=1)
        if modbus.get("status") == "success":
            return {
                "status": "healthy",
                "connectivity": {"latency_ms": conn.get("latency_ms", 0)},
                "modbus_test": {"status": "success", "latency_ms": modbus.get("latency_ms", 0)},
            }
        return {
            "status": "degraded",
            "connectivity": {"latency_ms": conn.get("latency_ms", 0)},
            "modbus_test": {"status": "error", "error": modbus.get("error", "unknown")},
        }

    def close(self):
        """Close the Modbus connection."""
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None


# ---------------------------------------------------------------------------
# HTTP API client (calls plc-modbus FastAPI service)
# ---------------------------------------------------------------------------

class EdgeGatewayAPIClient:
    """HTTP client that reads PLC data through the plc-modbus FastAPI service.

    Use this when the plc-modbus service is already managing the PLC
    connection (avoids duplicate TCP connections).

    Usage::

        client = EdgeGatewayAPIClient("192.168.1.100")
        data = client.read_plc_registers(100, 6)
    """

    def __init__(self, ip: str = DEFAULT_IP, api_port: int = PLC_API_PORT, timeout: int = TIMEOUT):
        self.base_url = f"http://{ip}:{api_port}/api"
        self.timeout = timeout

    def __repr__(self):
        return f"<EdgeGatewayAPIClient {self.base_url}>"

    def connect(self) -> Dict[str, Any]:
        """No-op for API mode — connection is managed by the FastAPI service."""
        return {"status": "connected", "latency_ms": 0}

    def read_plc_registers(
        self,
        register_start: int = 0,
        count: int = 0,
        slave_id: int = 1,
    ) -> Dict[str, Any]:
        """Read PLC I/O via the plc-modbus API ``GET /api/plc/io``."""
        import requests

        try:
            start = time.time()
            resp = requests.get(f"{self.base_url}/plc/io", timeout=self.timeout)
            latency_ms = round((time.time() - start) * 1000, 2)

            if resp.status_code != 200:
                return {"status": "error", "error": f"API returned {resp.status_code}: {resp.text}"}

            data = resp.json()
            registers = data.get("registers", {})

            # Flatten register dict values into a list for compatibility
            values = list(registers.values()) if isinstance(registers, dict) else registers
            return {"status": "success", "values": values, "raw": data, "latency_ms": latency_ms}
        except Exception as exc:
            logger.error("PLC API read failed: %s", exc)
            return {"status": "error", "error": str(exc)}

    def health_check(self) -> Dict[str, Any]:
        """Health check via the plc-modbus API ``GET /api/plc/status``."""
        import requests

        try:
            start = time.time()
            resp = requests.get(f"{self.base_url}/plc/status", timeout=self.timeout)
            latency_ms = round((time.time() - start) * 1000, 2)

            if resp.status_code != 200:
                return {
                    "status": "unhealthy",
                    "connectivity": {"status": "error", "error": f"API {resp.status_code}"},
                    "modbus_test": {"status": "skipped"},
                }

            data = resp.json()
            return {
                "status": "healthy" if data.get("connected") else "degraded",
                "connectivity": {"latency_ms": latency_ms},
                "modbus_test": {"status": "success" if data.get("connected") else "not_connected"},
                "raw": data,
            }
        except Exception as exc:
            logger.error("PLC API health check failed: %s", exc)
            return {
                "status": "unhealthy",
                "connectivity": {"status": "error", "error": str(exc)},
                "modbus_test": {"status": "skipped"},
            }

    def close(self):
        """No-op for API mode."""
        pass


# ---------------------------------------------------------------------------
# Factory — pick client based on EDGE_MODE env var
# ---------------------------------------------------------------------------

def get_client(ip: str = DEFAULT_IP) -> EdgeGatewayClient | EdgeGatewayAPIClient:
    """Return the appropriate client based on ``EDGE_MODE`` env var."""
    if EDGE_MODE == "api":
        return EdgeGatewayAPIClient(ip)
    return EdgeGatewayClient(ip)


# ---------------------------------------------------------------------------
# Module-level convenience functions (backwards compatible)
# ---------------------------------------------------------------------------

_default_client: EdgeGatewayClient | EdgeGatewayAPIClient | None = None


def _get_default_client(ip: str) -> EdgeGatewayClient | EdgeGatewayAPIClient:
    global _default_client
    if _default_client is None or (hasattr(_default_client, "ip") and _default_client.ip != ip):
        _default_client = get_client(ip)
    return _default_client


def connect_to_edge(ip: str) -> Dict[str, Any]:
    """Test connectivity to the edge gateway PLC."""
    client = _get_default_client(ip)
    return client.connect()


def read_plc_registers(
    register_start: int,
    count: int,
    slave_id: int = 1,
    ip: Optional[str] = None,
) -> Dict[str, Any]:
    """Read holding registers from the PLC."""
    target_ip = ip or DEFAULT_IP
    client = _get_default_client(target_ip)
    return client.read_plc_registers(register_start, count, slave_id)


def health_check(ip: str) -> Dict[str, Any]:
    """Full health check: connectivity + trial register read."""
    client = _get_default_client(ip)
    return client.health_check()
