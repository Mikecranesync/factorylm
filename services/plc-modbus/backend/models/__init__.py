"""Pydantic models for API requests and responses."""

from .scan_models import (
    DeviceInfo,
    ScanRequest,
    ScanResponse,
    ScanResult,
)

from .plc_models import (
    PLCStatusResponse,
    ConnectRequest,
    ConnectResponse,
    IOResponse,
    WriteCoilRequest,
    WriteCoilResponse,
)

__all__ = [
    "DeviceInfo",
    "ScanRequest",
    "ScanResponse",
    "ScanResult",
    "PLCStatusResponse",
    "ConnectRequest",
    "ConnectResponse",
    "IOResponse",
    "WriteCoilRequest",
    "WriteCoilResponse",
]
