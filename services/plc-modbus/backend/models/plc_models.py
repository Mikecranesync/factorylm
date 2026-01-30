"""Pydantic models for PLC API requests and responses."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class PLCStatusResponse(BaseModel):
    """Response model for PLC connection status."""

    connected: bool = Field(description="Whether PLC is connected")
    ip: Optional[str] = Field(default=None, description="PLC IP address")
    port: Optional[int] = Field(default=None, description="Modbus TCP port")
    last_seen: Optional[str] = Field(default=None, description="Last successful communication timestamp (ISO format)")


class ConnectRequest(BaseModel):
    """Request model for PLC connect endpoint."""

    ip: str = Field(description="PLC IP address", examples=["192.168.1.100"])
    port: int = Field(default=502, ge=1, le=65535, description="Modbus TCP port")


class ConnectResponse(BaseModel):
    """Response model for PLC connect endpoint."""

    success: bool = Field(description="Whether connection was successful")
    message: str = Field(description="Connection result message")


class CoilData(BaseModel):
    """Program variable coils (0-6)."""

    motor_running: bool = False
    motor_stopped: bool = False
    fault_alarm: bool = False
    conveyor_running: bool = False
    sensor_1_active: bool = False
    sensor_2_active: bool = False
    e_stop_active: bool = False


class InputData(BaseModel):
    """Physical input coils (7-14)."""

    DI_00: bool = False  # 3-pos switch CENTER
    DI_01: bool = False  # E-stop NO contact
    DI_02: bool = False  # E-stop NC contact
    DI_03: bool = False  # 3-pos switch RIGHT
    DI_04: bool = False  # Left Pushbutton
    DI_05: bool = False
    DI_06: bool = False
    DI_07: bool = False


class OutputData(BaseModel):
    """Physical output coils (15-17)."""

    DO_00: bool = False  # 3-pos indicator LED
    DO_01: bool = False  # E-stop indicator LED
    DO_03: bool = False  # Auxiliary output


class RegisterData(BaseModel):
    """Holding registers (100-105)."""

    motor_speed: int = 0
    motor_current: int = 0
    temperature: int = 0
    pressure: int = 0
    conveyor_speed: int = 0
    error_code: int = 0


class IOResponse(BaseModel):
    """Response model for I/O read endpoint."""

    coils: CoilData = Field(description="Program variable coils (0-6)")
    inputs: InputData = Field(description="Physical inputs (7-14)")
    outputs: OutputData = Field(description="Physical outputs (15-17)")
    registers: RegisterData = Field(description="Holding registers (100-105)")
    timestamp: str = Field(description="Read timestamp (ISO format)")


class WriteCoilRequest(BaseModel):
    """Request model for write coil endpoint."""

    address: int = Field(ge=0, le=17, description="Coil address to write")
    value: bool = Field(description="Value to write (True/False)")


class WriteCoilResponse(BaseModel):
    """Response model for write coil endpoint."""

    success: bool = Field(description="Whether write was successful")
    address: int = Field(description="Coil address that was written")
    value: bool = Field(description="Value that was written")
    name: str = Field(description="Name of the coil")
