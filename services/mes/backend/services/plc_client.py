"""Async HTTP client for the plc-modbus service.

The MES never talks Modbus TCP directly — it calls the plc-modbus
FastAPI service over HTTP.  This keeps the MES decoupled from hardware
and lets the plc-modbus service handle reconnection logic.

Endpoint used:
    GET {plc_modbus_url}/api/plc/io

Response shape (from plc-modbus IOResponse):
    {
        "coils":     {"Conveyor": bool, "RunCommand": bool, ...},
        "inputs":    {"DI_00": bool, ...},
        "outputs":   {"DO_00": bool, "DO_01": bool, ...},
        "registers": {
            "ItemCount":       int,   # cumulative part count at exit sensor
            "ConveyorHz":      int,   # VFD frequency (Hz)
            "MotorCurrentX10": int,   # motor current × 10 (e.g. 45 = 4.5 A)
            "MotorTempX10":    int,   # motor temp × 10 (e.g. 312 = 31.2 °C)
            "VFDStatus":       int,   # 0=idle  1=running  2=fault
            "ErrorCode":       int,   # 0=none  1=overload 2=overheat
                                      # 3=sensor 4=jam  7=e-stop
        },
        "timestamp": str,
    }
"""

import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# Timeout for each HTTP call to plc-modbus
_HTTP_TIMEOUT = 4.0  # seconds


class PLCOfflineError(Exception):
    """Raised when plc-modbus is unreachable or returns an error status."""


async def fetch_io(plc_modbus_url: str) -> dict:
    """Fetch a single IO snapshot from the plc-modbus service.

    Args:
        plc_modbus_url: Base URL of the plc-modbus service,
                        e.g. "http://plc-modbus:8001"

    Returns:
        Parsed JSON dict with keys: coils, inputs, outputs, registers, timestamp.

    Raises:
        PLCOfflineError: on connection error, timeout, or HTTP >= 400.
    """
    url = f"{plc_modbus_url.rstrip('/')}/api/plc/io"
    try:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            resp = await client.get(url)
        if resp.status_code >= 400:
            raise PLCOfflineError(
                f"plc-modbus returned HTTP {resp.status_code} for {url}"
            )
        return resp.json()
    except httpx.TimeoutException as exc:
        raise PLCOfflineError(f"Timeout reaching plc-modbus at {url}") from exc
    except httpx.ConnectError as exc:
        raise PLCOfflineError(f"Cannot connect to plc-modbus at {url}") from exc
    except PLCOfflineError:
        raise
    except Exception as exc:
        raise PLCOfflineError(f"Unexpected error fetching {url}: {exc}") from exc


def extract_registers(io_data: dict) -> dict:
    """Return the registers sub-dict, defaulting to empty."""
    return io_data.get("registers", {})


def extract_coils(io_data: dict) -> dict:
    """Return the coils sub-dict, defaulting to empty."""
    return io_data.get("coils", {})


def item_count(io_data: dict) -> int:
    """Cumulative part count from HR100 (ItemCount)."""
    return extract_registers(io_data).get("ItemCount", 0)
