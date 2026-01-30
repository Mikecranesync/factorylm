"""
Factory I/O + Micro 820 specialized client.

Provides Factory I/O scene-aware state reading with conveyor, sensor,
and e-stop support.
"""

from datetime import datetime
from typing import Dict

from .micro820 import Micro820PLC
from .models import FactoryState, ERROR_CODES


class FactoryIOMicro820(Micro820PLC):
    """
    Specialized client for Factory I/O + Micro 820 setup.

    Extends Micro820PLC with Factory I/O-specific registers, coils,
    and scene semantics.
    """

    # Register map matching CCW configuration
    REGISTERS: Dict[str, int] = {
        "motor_speed": 100,
        "motor_current": 101,
        "temperature": 102,
        "pressure": 103,
        "conveyor_speed": 104,
        "error_code": 105,
    }

    # Coil map matching CCW configuration
    COILS: Dict[str, int] = {
        "motor_running": 0,
        "motor_stopped": 1,
        "fault_alarm": 2,
        "conveyor_running": 3,
        "sensor_1": 4,
        "sensor_2": 5,
        "e_stop": 6,
    }

    # Scale factors (divide raw value)
    SCALE_FACTORS: Dict[str, float] = {
        "motor_current": 10.0,  # Raw 25 = 2.5A
        "temperature": 10.0,    # Raw 650 = 65.0C
    }

    def __init__(
        self,
        host: str,
        port: int = 502,
        timeout: float = 5.0,
        retries: int = 3,
        unit_id: int = 1,
        scene_name: str = "sorting_station",
    ):
        """
        Initialize FactoryIOMicro820 client.

        Args:
            host: PLC IP address or hostname.
            port: Modbus TCP port (default 502).
            timeout: Connection/read timeout in seconds.
            retries: Number of retry attempts for failed operations.
            unit_id: Modbus unit/slave ID (default 1).
            scene_name: Factory I/O scene name for context.
        """
        super().__init__(host, port, timeout, retries, unit_id)
        self.scene_name = scene_name

    @staticmethod
    def interpret_error_code(code: int) -> str:
        """
        Convert error code to human-readable message.

        Args:
            code: Error code from PLC.

        Returns:
            str: Human-readable error message.
        """
        return ERROR_CODES.get(code, f"Unknown error {code}")

    def read_state(self) -> FactoryState:
        """
        Read the complete Factory I/O state from the PLC.

        Returns:
            FactoryState: Current state with all Factory I/O values.
        """
        # Read all registers and coils
        registers = self.read_all_registers()
        coils = self.read_all_coils()

        # Get error code and interpret it
        error_code = int(registers.get("error_code", 0))
        error_message = self.interpret_error_code(error_code) if error_code else ""

        return FactoryState(
            # Motor state
            motor_running=coils.get("motor_running", False),
            motor_speed=int(registers.get("motor_speed", 0)),
            motor_current=registers.get("motor_current", 0.0),

            # Environmental
            temperature=registers.get("temperature", 0.0),
            pressure=int(registers.get("pressure", 0)),

            # Fault
            fault_active=coils.get("fault_alarm", False),

            # Conveyor
            conveyor_speed=int(registers.get("conveyor_speed", 0)),
            conveyor_running=coils.get("conveyor_running", False),

            # Sensors
            sensor_1_active=coils.get("sensor_1", False),
            sensor_2_active=coils.get("sensor_2", False),

            # Safety
            e_stop_active=coils.get("e_stop", False),

            # Error
            error_code=error_code,
            error_message=error_message,

            # Metadata
            timestamp=datetime.now(),
            scene_name=self.scene_name,
        )

    def start_motor(self, speed: int = 50) -> bool:
        """
        Start the motor at specified speed.

        Args:
            speed: Motor speed percentage (0-100).

        Returns:
            bool: True if successful.
        """
        # Set speed first, then start
        self.write_register_by_name("motor_speed", speed)
        return self.write_coil_by_name("motor_running", True)

    def stop_motor(self) -> bool:
        """
        Stop the motor.

        Returns:
            bool: True if successful.
        """
        return self.write_coil_by_name("motor_running", False)

    def start_conveyor(self, speed: int = 50) -> bool:
        """
        Start the conveyor at specified speed.

        Args:
            speed: Conveyor speed percentage (0-100).

        Returns:
            bool: True if successful.
        """
        self.write_register_by_name("conveyor_speed", speed)
        return self.write_coil_by_name("conveyor_running", True)

    def stop_conveyor(self) -> bool:
        """
        Stop the conveyor.

        Returns:
            bool: True if successful.
        """
        return self.write_coil_by_name("conveyor_running", False)

    def clear_error(self) -> bool:
        """
        Clear the current error code.

        Returns:
            bool: True if successful.
        """
        return self.write_register_by_name("error_code", 0)

    def acknowledge_fault(self) -> bool:
        """
        Acknowledge and clear the fault alarm.

        Returns:
            bool: True if successful.
        """
        self.clear_error()
        return self.write_coil_by_name("fault_alarm", False)

    def is_estop_active(self) -> bool:
        """
        Check if emergency stop is active.

        Returns:
            bool: True if e-stop is engaged.
        """
        return self.read_coil_by_name("e_stop")

    def get_sensor_states(self) -> Dict[str, bool]:
        """
        Get the current state of all sensors.

        Returns:
            Dict[str, bool]: Sensor name to state mapping.
        """
        return {
            "sensor_1": self.read_coil_by_name("sensor_1"),
            "sensor_2": self.read_coil_by_name("sensor_2"),
        }

    def get_error_status(self) -> Dict[str, any]:
        """
        Get the current error status.

        Returns:
            Dict with error_code, error_message, and fault_active.
        """
        error_code = int(self.read_register_by_name("error_code"))
        return {
            "error_code": error_code,
            "error_message": self.interpret_error_code(error_code),
            "fault_active": self.read_coil_by_name("fault_alarm"),
        }
