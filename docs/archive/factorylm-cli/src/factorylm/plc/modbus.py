"""Modbus TCP PLC client (pymodbus).

Supports generic Modbus and Allen-Bradley Micro 820 register mapping.
"""

from __future__ import annotations

import logging
from typing import Any

from factorylm.plc.base import BasePLCClient

logger = logging.getLogger(__name__)

# Default register map (Micro 820 convention)
DEFAULT_REGISTERS: dict[str, int] = {
    "motor_speed": 100,
    "motor_current": 101,
    "temperature": 102,
    "pressure": 103,
    "conveyor_speed": 104,
    "error_code": 105,
}

DEFAULT_COILS: dict[str, int] = {
    "motor_running": 0,
    "motor_stopped": 1,
    "fault_alarm": 2,
    "conveyor_running": 3,
    "sensor_1": 4,
    "sensor_2": 5,
    "e_stop": 6,
}

SCALE_FACTORS: dict[str, float] = {
    "motor_current": 10.0,
    "temperature": 10.0,
}


class ModbusPLCClient(BasePLCClient):
    """Modbus TCP client wrapping pymodbus."""

    def __init__(
        self,
        host: str = "192.168.1.100",
        port: int = 502,
        unit_id: int = 1,
        timeout: float = 5.0,
        retries: int = 3,
        registers: dict[str, int] | None = None,
        coils: dict[str, int] | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.unit_id = unit_id
        self.timeout = timeout
        self.retries = retries
        self.registers = registers or DEFAULT_REGISTERS
        self.coils = coils or DEFAULT_COILS
        self._client = None
        self._connected = False

    def connect(self) -> bool:
        try:
            from pymodbus.client import ModbusTcpClient

            self._client = ModbusTcpClient(
                host=self.host,
                port=self.port,
                timeout=self.timeout,
                retries=self.retries,
            )
            self._connected = self._client.connect()
            if self._connected:
                logger.info("Connected to Modbus PLC at %s:%d", self.host, self.port)
            else:
                logger.warning("Failed to connect to %s:%d", self.host, self.port)
            return self._connected
        except ImportError:
            logger.error("pymodbus not installed. Run: pip install 'factorylm[modbus]'")
            return False
        except Exception as e:
            logger.error("Modbus connection error: %s", e)
            self._connected = False
            return False

    def disconnect(self) -> None:
        if self._client:
            self._client.close()
            self._connected = False

    def is_connected(self) -> bool:
        if not self._client:
            return False
        return self._connected and self._client.connected

    def _ensure_connected(self) -> None:
        if not self.is_connected():
            raise ConnectionError(f"Not connected to PLC at {self.host}:{self.port}")

    def read_tags(self) -> dict[str, Any]:
        """Read all registers and coils, return as flat tag dict."""
        self._ensure_connected()
        data: dict[str, Any] = {}

        # Read registers
        if self.registers:
            addresses = sorted(self.registers.values())
            start = addresses[0]
            count = addresses[-1] - start + 1
            result = self._client.read_holding_registers(
                address=start, count=count, slave=self.unit_id,
            )
            if not result.isError():
                for name, addr in self.registers.items():
                    idx = addr - start
                    if 0 <= idx < len(result.registers):
                        raw = result.registers[idx]
                        if name in SCALE_FACTORS:
                            data[name] = raw / SCALE_FACTORS[name]
                        else:
                            data[name] = raw

        # Read coils
        if self.coils:
            addresses = sorted(self.coils.values())
            start = addresses[0]
            count = addresses[-1] - start + 1
            result = self._client.read_coils(
                address=start, count=count, slave=self.unit_id,
            )
            if not result.isError():
                for name, addr in self.coils.items():
                    idx = addr - start
                    if 0 <= idx < len(result.bits):
                        data[name] = bool(result.bits[idx])

        return data

    def write_tag(self, name: str, value: Any) -> bool:
        self._ensure_connected()

        if name in self.registers:
            addr = self.registers[name]
            if name in SCALE_FACTORS:
                raw = int(float(value) * SCALE_FACTORS[name])
            else:
                raw = int(value)
            result = self._client.write_register(
                address=addr, value=raw, slave=self.unit_id,
            )
            return not result.isError()

        if name in self.coils:
            addr = self.coils[name]
            result = self._client.write_coil(
                address=addr, value=bool(value), slave=self.unit_id,
            )
            return not result.isError()

        raise ValueError(f"Unknown tag: {name}")
