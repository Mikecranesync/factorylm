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
    """Program variable coils (0-6) — From A to B scene."""

    Conveyor: bool = False       # Coil 0: belt motor output
    Emitter: bool = False        # Coil 1: item spawner output
    SensorStart: bool = False    # Coil 2: entry sensor input
    SensorEnd: bool = False      # Coil 3: exit sensor input
    RunCommand: bool = False     # Coil 4: remote start/stop
    program_var_5: bool = False
    program_var_6: bool = False


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

    ItemCount: int = 0
    register_101: int = 0
    register_102: int = 0
    register_103: int = 0
    register_104: int = 0
    register_105: int = 0


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
