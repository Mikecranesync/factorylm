"""Siemens S7 PLC client using python-snap7.

Supports S7-1200 and S7-1500 controllers.
"""

from __future__ import annotations

import logging
from typing import Any

from factorylm.plc.base import BasePLCClient

logger = logging.getLogger(__name__)

# Default data block tags: (db_number, start_byte, size_bytes, data_type, tag_name)
DEFAULT_TAGS: list[tuple[int, int, int, str, str]] = [
    (1, 0, 4, "REAL", "motor_speed"),
    (1, 4, 4, "REAL", "motor_temp"),
    (1, 8, 4, "REAL", "vibration"),
    (1, 12, 4, "REAL", "current"),
]


class S7Client(BasePLCClient):
    """Siemens S7 client wrapping python-snap7."""

    def __init__(
        self,
        host: str = "192.168.0.1",
        port: int = 102,
        rack: int = 0,
        slot: int = 1,
        tags: list[tuple[int, int, int, str, str]] | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.rack = rack
        self.slot = slot
        self.tags = tags or list(DEFAULT_TAGS)
        self._client = None
        self._connected = False

    def connect(self) -> bool:
        try:
            import snap7

            self._client = snap7.client.Client()
            self._client.connect(self.host, self.rack, self.slot)
            self._connected = self._client.get_connected()
            if self._connected:
                logger.info("Connected to S7 PLC at %s (rack=%d slot=%d)", self.host, self.rack, self.slot)
            return self._connected
        except ImportError:
            logger.error("snap7 not installed. Run: pip install 'factorylm[s7]'")
            return False
        except Exception as e:
            logger.error("S7 connection failed: %s", e)
            self._connected = False
            return False

    def disconnect(self) -> None:
        if self._client:
            try:
                self._client.disconnect()
            except Exception:
                pass
            self._connected = False

    def is_connected(self) -> bool:
        if not self._client:
            return False
        try:
            return self._connected and self._client.get_connected()
        except Exception:
            return False

    def read_tags(self) -> dict[str, Any]:
        if not self.is_connected():
            raise ConnectionError("Not connected to PLC")

        from snap7.util import get_real, get_int, get_bool

        data: dict[str, Any] = {}
        for db_num, start, size, dtype, tag_name in self.tags:
            try:
                raw = self._client.db_read(db_num, start, size)
                if dtype == "REAL":
                    value = round(get_real(raw, 0), 3)
                elif dtype == "INT":
                    value = get_int(raw, 0)
                elif dtype == "BOOL":
                    value = get_bool(raw, 0, 0)
                else:
                    value = raw.hex()
                data[tag_name] = value
            except Exception as e:
                logger.warning("Failed to read %s: %s", tag_name, e)
                data[tag_name] = None

        return data

    def write_tag(self, name: str, value: Any) -> bool:
        if not self.is_connected():
            raise ConnectionError("Not connected to PLC")

        import struct
        from snap7.util import set_real, set_int, set_bool

        for db_num, start, size, dtype, tag_name in self.tags:
            if tag_name != name:
                continue
            try:
                data = bytearray(size)
                if dtype == "REAL":
                    set_real(data, 0, float(value))
                elif dtype == "INT":
                    set_int(data, 0, int(value))
                elif dtype == "BOOL":
                    set_bool(data, 0, 0, bool(value))
                else:
                    return False
                self._client.db_write(db_num, start, data)
                return True
            except Exception as e:
                logger.error("S7 write failed for %s: %s", name, e)
                return False

        raise ValueError(f"Unknown tag: {name}")
