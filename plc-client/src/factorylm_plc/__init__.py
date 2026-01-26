"""
FactoryLM PLC Client - Industrial I/O Layer

Provides unified access to industrial PLCs via Modbus TCP.
Supports Micro820 out-of-box with extensible interface for other PLCs.
"""

__version__ = "0.3.0"

from .plc.base import BasePLCClient

# MachineState imported when available (PLC-003)
try:
    from .models import MachineState
except ImportError:
    MachineState = None  # type: ignore

__all__ = [
    "MachineState",
    "BasePLCClient",
    "create_plc_client",
]


def create_plc_client(plc_type: str, host: str = "", port: int = 502) -> BasePLCClient:
    """
    Factory function to create appropriate PLC client.

    Args:
        plc_type: Type of PLC ("micro820", "mock")
        host: IP address of the PLC (not needed for mock)
        port: Modbus TCP port (default 502)

    Returns:
        BasePLCClient: Configured PLC client instance

    Raises:
        ValueError: If plc_type is unknown
    """
    if plc_type == "micro820":
        from .plc.micro820 import Micro820PLC
        return Micro820PLC(host, port)
    elif plc_type == "mock":
        from .plc.mock_plc import MockPLC
        return MockPLC()
    else:
        raise ValueError(f"Unknown PLC type: {plc_type}")
