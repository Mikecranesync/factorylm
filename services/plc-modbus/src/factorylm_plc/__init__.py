"""
FactoryLM PLC Client - Factory I/O + Micro 820 Integration Layer

A Python library for connecting Factory I/O simulation to Allen-Bradley
Micro 820 PLC via Modbus TCP, with LLM4PLC integration for Structured Text
code generation.
"""

from .models import MachineState, FactoryState
from .base import BasePLCClient
from .modbus_client import ModbusTCPClient
from .mock_plc import MockPLC
from .micro820 import Micro820PLC
from .factory_io import FactoryIOMicro820
from .connection_manager import PLCConnectionManager
from .factory import create_plc_client
from .llm4plc import (
    STProgram,
    STVariable,
    STDataType,
    STCodeGenerator,
    create_program_from_template,
    generate_conveyor_control,
    generate_motor_safety_program,
    generate_sorting_station_program,
)

__version__ = "0.4.0"
__all__ = [
    # Data models
    "MachineState",
    "FactoryState",
    # Clients
    "BasePLCClient",
    "ModbusTCPClient",
    "MockPLC",
    "Micro820PLC",
    "FactoryIOMicro820",
    # Utilities
    "PLCConnectionManager",
    "create_plc_client",
    # LLM4PLC Integration
    "STProgram",
    "STVariable",
    "STDataType",
    "STCodeGenerator",
    "create_program_from_template",
    "generate_conveyor_control",
    "generate_motor_safety_program",
    "generate_sorting_station_program",
]
