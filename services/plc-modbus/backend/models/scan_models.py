"""Pydantic models for network scan requests and responses."""

from typing import Literal, Optional

from pydantic import BaseModel, Field


class ScanRequest(BaseModel):
    """Request model for network scan endpoint."""

    subnet: str = Field(
        default="192.168.1",
        description="Subnet prefix (e.g., '192.168.1')",
        examples=["192.168.1", "10.0.0"],
    )
    start: int = Field(
        default=1,
        ge=1,
        le=254,
        description="Starting IP address suffix",
    )
    end: int = Field(
        default=254,
        ge=1,
        le=254,
        description="Ending IP address suffix",
    )
    timeout: float = Field(
        default=0.3,
        gt=0,
        le=5.0,
        description="Connection timeout in seconds",
    )


class ScanResult(BaseModel):
    """Internal result from probing a single IP."""

    ip: str
    port: int
    status: Literal["online", "timeout", "connection_refused", "error"]
    response_time_ms: Optional[float] = None
    error_message: Optional[str] = None


class DeviceInfo(BaseModel):
    """Information about a discovered Modbus device."""

    ip: str = Field(description="IP address of the device")
    port: int = Field(default=502, description="Modbus TCP port")
    status: Literal["online"] = Field(default="online")
    response_time_ms: float = Field(description="Response time in milliseconds")


class ScanResponse(BaseModel):
    """Response model for network scan endpoint."""

    devices: list[DeviceInfo] = Field(
        default_factory=list,
        description="List of discovered online Modbus devices",
    )
    count: int = Field(description="Total number of IPs scanned")
    online_count: int = Field(description="Number of online devices found")
    scan_time_seconds: float = Field(description="Total scan duration in seconds")
    subnet_scanned: str = Field(description="Subnet range that was scanned")
