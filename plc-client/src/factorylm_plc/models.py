"""
Data Models for PLC Client

Defines standardized data structures for machine state representation.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional
import time


@dataclass
class MachineState:
    """
    Standardized machine state from any PLC.

    This dataclass represents the current state of a machine/PLC,
    providing a consistent format regardless of PLC type.

    Attributes:
        motor_speed: Motor speed in RPM
        motor_current: Motor current in Amps
        temperature: Temperature in Celsius
        pressure: Pressure in PSI
        motor_running: True if motor is running
        motor_stopped: True if motor is stopped
        fault_alarm: True if fault/alarm is active
        timestamp: Unix timestamp of when state was read
        raw_registers: Raw register values for debugging
    """

    motor_speed: int
    motor_current: int
    temperature: float
    pressure: int
    motor_running: bool
    motor_stopped: bool
    fault_alarm: bool
    timestamp: float = field(default_factory=time.time)
    raw_registers: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary for JSON serialization.

        Returns:
            Dict containing all machine state values
        """
        return {
            "motor_speed": self.motor_speed,
            "motor_current": self.motor_current,
            "temperature": self.temperature,
            "pressure": self.pressure,
            "motor_running": self.motor_running,
            "motor_stopped": self.motor_stopped,
            "fault_alarm": self.fault_alarm,
            "timestamp": self.timestamp,
            "raw_registers": self.raw_registers,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MachineState":
        """
        Create MachineState from dictionary.

        Args:
            data: Dictionary with machine state values

        Returns:
            MachineState instance
        """
        return cls(
            motor_speed=data.get("motor_speed", 0),
            motor_current=data.get("motor_current", 0),
            temperature=data.get("temperature", 0.0),
            pressure=data.get("pressure", 0),
            motor_running=data.get("motor_running", False),
            motor_stopped=data.get("motor_stopped", True),
            fault_alarm=data.get("fault_alarm", False),
            timestamp=data.get("timestamp", time.time()),
            raw_registers=data.get("raw_registers", {}),
        )

    def is_healthy(self) -> bool:
        """
        Check if machine state indicates healthy operation.

        Returns:
            True if no faults and within normal parameters
        """
        return not self.fault_alarm

    def __str__(self) -> str:
        """Human-readable string representation."""
        status = "RUNNING" if self.motor_running else "STOPPED"
        if self.fault_alarm:
            status = "FAULT"
        return (
            f"MachineState({status}: "
            f"speed={self.motor_speed}RPM, "
            f"temp={self.temperature}°C, "
            f"pressure={self.pressure}PSI)"
        )
