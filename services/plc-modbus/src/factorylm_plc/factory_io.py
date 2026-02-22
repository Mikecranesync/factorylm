"""
Factory I/O + Micro 820 specialized client.

Provides Factory I/O scene-aware state reading with conveyor, sensor,
and e-stop support.

Register map summary (19 total):
  Holding registers (9): motor_speed, motor_current, temperature, pressure,
      conveyor_speed, error_code, part_count, production_rate, cycle_time_ms
  Coils (10): motor_running, motor_stopped, fault_alarm, conveyor_running,
      sensor_1, sensor_2, e_stop, entry_sensor, estop_contact_no,
      selector_switch_right
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

    Total mapped I/O: 19 (9 holding registers + 10 coils).
    """

    # Register map matching CCW configuration (9 holding registers)
    REGISTERS: Dict[str, int] = {
        # --- Original 6 registers ---
        "motor_speed": 100,       # Motor speed 0-100%
        "motor_current": 101,     # Motor current (raw / 10 = Amps)
        "temperature": 102,       # Temperature (raw / 10 = degC)
        "pressure": 103,          # Pressure (PSI)
        "conveyor_speed": 104,    # Conveyor belt speed 0-100%
        "error_code": 105,        # 0=OK,1=Overload,2=Overheat,3=Jam,4=Sensor,5=Comms
        # --- Added registers (brings total to 9 holding registers) ---
        "part_count": 106,        # Parts processed since last reset (cumulative)
        "production_rate": 107,   # Parts per minute (rolling 60-second window)
        "cycle_time_ms": 108,     # Last part cycle time in milliseconds
    }

    # Coil map matching CCW configuration (10 coils)
    COILS: Dict[str, int] = {
        # --- Original 7 coils (program variables, addresses 0-6) ---
        "motor_running": 0,
        "motor_stopped": 1,
        "fault_alarm": 2,
        "conveyor_running": 3,
        "sensor_1": 4,
        "sensor_2": 5,
        "e_stop": 6,
        # --- Added coils: physical I/O mapped per CCW address map (addresses 7-10) ---
        "entry_sensor": 7,            # _IO_EM_DI_00 — 3-pos switch CENTER / entry detect
        "estop_contact_no": 8,        # _IO_EM_DI_01 — E-stop NO contact (ON when pressed)
        "selector_switch_right": 10,  # _IO_EM_DI_03 — 3-pos switch RIGHT detect
    }

    # Scale factors (divide raw value by this factor)
    SCALE_FACTORS: Dict[str, float] = {
        "motor_current": 10.0,  # Raw 25 = 2.5A
        "temperature": 10.0,    # Raw 650 = 65.0C
        # part_count, production_rate, cycle_time_ms are stored as raw integers
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

            # Sensors (program coils)
            sensor_1_active=coils.get("sensor_1", False),
            sensor_2_active=coils.get("sensor_2", False),

            # Physical I/O coils (added)
            entry_sensor_active=coils.get("entry_sensor", False),
            estop_contact_no=coils.get("estop_contact_no", False),
            selector_switch_right=coils.get("selector_switch_right", False),

            # Safety
            e_stop_active=coils.get("e_stop", False),

            # Production counters (added)
            part_count=int(registers.get("part_count", 0)),
            production_rate=int(registers.get("production_rate", 0)),
            cycle_time_ms=int(registers.get("cycle_time_ms", 0)),

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

        Includes both program-variable coils (sensor_1/2) and physical
        I/O coils (entry_sensor, estop_contact_no, selector_switch_right).

        Returns:
            Dict[str, bool]: Sensor name to state mapping.
        """
        return {
            "sensor_1": self.read_coil_by_name("sensor_1"),
            "sensor_2": self.read_coil_by_name("sensor_2"),
            "entry_sensor": self.read_coil_by_name("entry_sensor"),
            "estop_contact_no": self.read_coil_by_name("estop_contact_no"),
            "selector_switch_right": self.read_coil_by_name("selector_switch_right"),
        }

    def get_production_stats(self) -> Dict[str, int]:
        """
        Get current production statistics.

        Returns:
            Dict with part_count, production_rate (parts/min), and cycle_time_ms.
        """
        return {
            "part_count": int(self.read_register_by_name("part_count")),
            "production_rate": int(self.read_register_by_name("production_rate")),
            "cycle_time_ms": int(self.read_register_by_name("cycle_time_ms")),
        }

    def reset_part_count(self) -> bool:
        """
        Reset the part count register to zero.

        Returns:
            bool: True if successful.
        """
        return self.write_register_by_name("part_count", 0)

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
