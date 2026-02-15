"""
Digital Twin Node Routing System for PEPPER (FactoryLM)

This package provides digital twin representations for all devices in the FactoryLM
ecosystem, enabling intelligent routing, health monitoring, and remote execution.

Each digital twin represents a physical device (PLC laptop, Travel laptop, VPS) and
knows its capabilities, health status, and communication protocols.
"""

from .twin import DigitalTwin, TwinStatus
from .registry import TwinRegistry
from .plc_twin import PLCTwin
from .travel_twin import TravelTwin
from .vps_twin import VPSTwin

__all__ = [
    "DigitalTwin",
    "TwinStatus",
    "TwinRegistry",
    "PLCTwin",
    "TravelTwin",
    "VPSTwin",
]
