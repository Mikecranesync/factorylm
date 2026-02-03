"""
Data models for PLC state representation.

Provides dataclasses for representing machine state with LLM-ready formatting.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, Dict, Any


@dataclass
class MachineState:
    """
    Base machine state dataclass.

    Represents the core state of an industrial machine including motor,
    temperature, and pressure readings.
    """
    # Motor state
    motor_running: bool = False
    motor_speed: int = 0
    motor_current: float = 0.0

    # Environmental readings
    temperature: float = 0.0
    pressure: int = 0

    # Fault state
    fault_active: bool = False

    # Metadata
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert state to dictionary for JSON serialization."""
        result = asdict(self)
        result["timestamp"] = self.timestamp.isoformat()
        return result

    def to_llm_context(self) -> str:
        """Format state for LLM prompt injection."""
        status = "RUNNING" if self.motor_running else "STOPPED"
        speed_str = f" at {self.motor_speed}%" if self.motor_running else ""

        return f"""Current Machine State:
- Motor: {status}{speed_str}
- Motor Current: {self.motor_current}A
- Temperature: {self.temperature}C
- Pressure: {self.pressure} PSI
- Fault: {'ACTIVE!' if self.fault_active else 'None'}
- Timestamp: {self.timestamp.strftime('%H:%M:%S')}"""


# Error code definitions for Factory I/O
ERROR_CODES: Dict[int, str] = {
    0: "No error",
    1: "Motor overload",
    2: "Temperature high",
    3: "Conveyor jam",
    4: "Sensor failure",
    5: "Communication loss",
}


@dataclass
class FactoryState(MachineState):
    """
    Extended state for Factory I/O scenes.

    Includes conveyor, sensors, e-stop, and error code interpretation
    specific to Factory I/O simulation.
    """
    # Conveyor state
    conveyor_speed: int = 0
    conveyor_running: bool = False

    # Sensor states
    sensor_1_active: bool = False
    sensor_2_active: bool = False

    # Safety
    e_stop_active: bool = False

    # Error handling
    error_code: int = 0
    error_message: str = ""

    # Factory I/O scene identifier
    scene_name: str = "sorting_station"

    def __post_init__(self):
        """Populate error_message from error_code if not set."""
        if self.error_code and not self.error_message:
            self.error_message = self.interpret_error_code(self.error_code)

    @staticmethod
    def interpret_error_code(code: int) -> str:
        """Convert error code to human-readable message."""
        return ERROR_CODES.get(code, f"Unknown error {code}")

    def to_dict(self) -> Dict[str, Any]:
        """Convert state to dictionary for JSON serialization."""
        result = super().to_dict()
        result["error_message"] = self.error_message or self.interpret_error_code(self.error_code)
        return result

    def to_llm_context(self) -> str:
        """Format state for LLM prompt injection with Factory I/O details."""
        # Motor status
        if self.motor_running:
            motor_str = f"RUNNING at {self.motor_speed}%"
        else:
            motor_str = "STOPPED"

        # Conveyor status
        if self.conveyor_running:
            conveyor_str = f"RUNNING at {self.conveyor_speed}%"
        else:
            conveyor_str = "STOPPED"

        # Sensor status
        s1 = "PART" if self.sensor_1_active else "clear"
        s2 = "PART" if self.sensor_2_active else "clear"

        # E-stop status
        estop_str = "ENGAGED!" if self.e_stop_active else "Clear"

        # Error status
        if self.error_code:
            error_str = self.error_message or self.interpret_error_code(self.error_code)
        else:
            error_str = "None"

        return f"""Current Factory State ({self.scene_name}):
- Motor: {motor_str}
- Motor Current: {self.motor_current}A
- Temperature: {self.temperature}C
- Pressure: {self.pressure} PSI
- Conveyor: {conveyor_str}
- Sensors: S1={s1}, S2={s2}
- E-Stop: {estop_str}
- Errors: {error_str}
- Timestamp: {self.timestamp.strftime('%H:%M:%S')}"""
