"""
FactoryLM PLC Client - Factory I/O + Micro 820 Integration Layer

A Python library for connecting Factory I/O simulation to Allen-Bradley
Micro 820 PLC via Modbus TCP, with LLM4PLC integration for Structured Text
code generation.

Hardware-facing exports are imported lazily (PEP 562 ``__getattr__``) so that
pure data-reshaping modules — ``factorylm_plc.machine_snapshot`` in
particular — can be imported without dragging in fieldbus dependencies like
``pymodbus`` (factorylm issue #202). ``from factorylm_plc import X`` still
works for every name in ``__all__``.
"""

from importlib import import_module

from .models import FactoryState, MachineState

_LAZY_EXPORTS = {
    "BasePLCClient": ".base",
    "ModbusTCPClient": ".modbus_client",
    "MockPLC": ".mock_plc",
    "Micro820PLC": ".micro820",
    "FactoryIOMicro820": ".factory_io",
    "PLCConnectionManager": ".connection_manager",
    "create_plc_client": ".factory",
    "STProgram": ".llm4plc",
    "STVariable": ".llm4plc",
    "STDataType": ".llm4plc",
    "STCodeGenerator": ".llm4plc",
    "create_program_from_template": ".llm4plc",
    "generate_conveyor_control": ".llm4plc",
    "generate_motor_safety_program": ".llm4plc",
    "generate_sorting_station_program": ".llm4plc",
}

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


def __getattr__(name: str):
    module_name = _LAZY_EXPORTS.get(name)
    if module_name is None:
        raise AttributeError("module %r has no attribute %r" % (__name__, name))
    module = import_module(module_name, __name__)
    value = getattr(module, name)
    globals()[name] = value
    return value


def __dir__():
    return sorted(set(globals()) | set(_LAZY_EXPORTS))
