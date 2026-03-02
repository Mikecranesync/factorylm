"""EtherNet/IP (Allen-Bradley) PLC client using pycomm3.

Supports CompactLogix, Micro820, and other AB controllers.
"""

from __future__ import annotations

import logging
from typing import Any

from factorylm.plc.base import BasePLCClient

logger = logging.getLogger(__name__)

DEFAULT_TAGS = [
    "Motor_Speed",
    "Motor_Temp",
    "Vibration",
    "Current",
    "Run_Status",
]


class EtherNetIPClient(BasePLCClient):
    """Allen-Bradley EtherNet/IP client wrapping pycomm3."""

    def __init__(
        self,
        host: str = "192.168.0.2",
        port: int = 44818,
        tags: list[str] | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.tags = tags or list(DEFAULT_TAGS)
        self._plc = None
        self._connected = False

    def connect(self) -> bool:
        try:
            from pycomm3 import LogixDriver

            self._plc = LogixDriver(self.host)
            self._plc.open()
            self._connected = True
            logger.info("Connected to AB PLC at %s (EtherNet/IP)", self.host)
            return True
        except ImportError:
            logger.error("pycomm3 not installed. Run: pip install 'factorylm[enip]'")
            return False
        except Exception as e:
            logger.error("EtherNet/IP connection failed: %s", e)
            self._connected = False
            return False

    def disconnect(self) -> None:
        if self._plc:
            try:
                self._plc.close()
            except Exception:
                pass
            self._connected = False

    def is_connected(self) -> bool:
        return self._connected and self._plc is not None

    def read_tags(self) -> dict[str, Any]:
        if not self.is_connected():
            raise ConnectionError("Not connected to PLC")

        data: dict[str, Any] = {}
        results = self._plc.read(*self.tags)
        if not isinstance(results, list):
            results = [results]

        for result in results:
            if result.error:
                logger.warning("Failed to read %s: %s", result.tag, result.error)
                data[result.tag] = None
            else:
                value = result.value
                if isinstance(value, float):
                    value = round(value, 3)
                data[result.tag] = value

        return data

    def write_tag(self, name: str, value: Any) -> bool:
        if not self.is_connected():
            raise ConnectionError("Not connected to PLC")

        try:
            result = self._plc.write(name, value)
            if isinstance(result, list):
                return all(not r.error for r in result)
            return not result.error
        except Exception as e:
            logger.error("EtherNet/IP write failed for %s: %s", name, e)
            return False
