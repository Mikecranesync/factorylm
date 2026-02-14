"""
Modbus Control Module
=====================
Direct Modbus TCP control of Factory I/O for fault injection.
"""

import logging
from typing import Dict, Any, Optional
from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException

from .config import PLC_HOST, MODBUS_PORT

logger = logging.getLogger(__name__)


class ModbusController:
    """
    Low-level Modbus TCP controller for fault injection.

    Provides direct access to coils and registers for creating
    specific fault conditions in Factory I/O.
    """

    # Coil addresses (matching Factory I/O Modbus server)
    COILS = {
        "motor_running": 0,
        "motor_stopped": 1,
        "fault_alarm": 2,
        "conveyor_running": 3,
        "sensor_1": 4,
        "sensor_2": 5,
        "e_stop": 6,
    }

    # Register addresses
    REGISTERS = {
        "motor_speed": 100,
        "motor_current": 101,
        "temperature": 102,
        "pressure": 103,
        "conveyor_speed": 104,
        "error_code": 105,
    }

    # Error codes for injection
    ERROR_CODES = {
        "none": 0,
        "motor_overload": 1,
        "sensor_failure": 2,
        "communication_error": 3,
        "overheat": 4,
        "low_pressure": 5,
        "conveyor_jam": 6,
        "emergency_stop": 7,
    }

    def __init__(self, host: str = None, port: int = None):
        """
        Initialize Modbus controller.

        Args:
            host: PLC host (default from config)
            port: Modbus port (default from config)
        """
        self.host = host or PLC_HOST
        self.port = port or MODBUS_PORT
        self.client: Optional[ModbusTcpClient] = None

    def connect(self) -> bool:
        """Connect to Modbus TCP server."""
        try:
            self.client = ModbusTcpClient(
                host=self.host,
                port=self.port,
                timeout=5
            )
            connected = self.client.connect()
            if connected:
                logger.info(f"Connected to Modbus at {self.host}:{self.port}")
            return connected
        except Exception as e:
            logger.error(f"Modbus connection failed: {e}")
            return False

    def disconnect(self):
        """Disconnect from Modbus server."""
        if self.client:
            self.client.close()
            self.client = None
            logger.info("Modbus disconnected")

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *args):
        self.disconnect()

    # ========================================================================
    # Low-level Read/Write
    # ========================================================================

    def read_coil(self, name: str) -> bool:
        """Read a coil by name."""
        addr = self.COILS.get(name)
        if addr is None:
            raise ValueError(f"Unknown coil: {name}")

        result = self.client.read_coils(address=addr, count=1)
        if result.isError():
            raise ModbusException(f"Failed to read coil {name}")
        return result.bits[0]

    def write_coil(self, name: str, value: bool) -> bool:
        """Write a coil by name."""
        addr = self.COILS.get(name)
        if addr is None:
            raise ValueError(f"Unknown coil: {name}")

        result = self.client.write_coil(address=addr, value=value)
        if result.isError():
            raise ModbusException(f"Failed to write coil {name}")
        logger.debug(f"Wrote coil {name}={value}")
        return True

    def read_register(self, name: str) -> int:
        """Read a holding register by name."""
        addr = self.REGISTERS.get(name)
        if addr is None:
            raise ValueError(f"Unknown register: {name}")

        result = self.client.read_holding_registers(address=addr, count=1)
        if result.isError():
            raise ModbusException(f"Failed to read register {name}")
        return result.registers[0]

    def write_register(self, name: str, value: int) -> bool:
        """Write a holding register by name."""
        addr = self.REGISTERS.get(name)
        if addr is None:
            raise ValueError(f"Unknown register: {name}")

        result = self.client.write_register(address=addr, value=value)
        if result.isError():
            raise ModbusException(f"Failed to write register {name}")
        logger.debug(f"Wrote register {name}={value}")
        return True

    # ========================================================================
    # High-level State Reading
    # ========================================================================

    def read_all_state(self) -> Dict[str, Any]:
        """Read complete Factory I/O state."""
        state = {}

        # Read all coils
        for name in self.COILS:
            try:
                state[name] = self.read_coil(name)
            except Exception:
                state[name] = None

        # Read all registers
        for name in self.REGISTERS:
            try:
                state[name] = self.read_register(name)
            except Exception:
                state[name] = None

        return state

    # ========================================================================
    # Fault Injection Methods
    # ========================================================================

    def inject_motor_overload(self):
        """
        Simulate motor overload fault.
        - Sets high motor current
        - Triggers fault alarm
        - Sets error code
        """
        logger.info("Injecting MOTOR OVERLOAD fault")
        self.write_register("motor_current", 120)  # 12.0A (over 10A limit)
        self.write_register("error_code", self.ERROR_CODES["motor_overload"])
        self.write_coil("fault_alarm", True)

    def inject_overheat(self):
        """
        Simulate overheating fault.
        - Sets high temperature
        - Triggers fault alarm
        - Sets error code
        """
        logger.info("Injecting OVERHEAT fault")
        self.write_register("temperature", 850)  # 85.0C (over 80C limit)
        self.write_register("error_code", self.ERROR_CODES["overheat"])
        self.write_coil("fault_alarm", True)

    def inject_sensor_jam(self):
        """
        Simulate sensor 1 jam (box stuck).
        - Sensor 1 stays triggered
        - Motor stops
        - Sets conveyor jam error
        """
        logger.info("Injecting SENSOR JAM fault")
        self.write_coil("sensor_1", True)  # Sensor blocked
        self.write_coil("motor_running", False)
        self.write_coil("conveyor_running", False)
        self.write_register("error_code", self.ERROR_CODES["conveyor_jam"])
        self.write_coil("fault_alarm", True)

    def inject_low_pressure(self):
        """
        Simulate low pressure fault.
        - Sets low pressure reading
        - Triggers fault alarm
        """
        logger.info("Injecting LOW PRESSURE fault")
        self.write_register("pressure", 50)  # 50 PSI (under 70 PSI limit)
        self.write_register("error_code", self.ERROR_CODES["low_pressure"])
        self.write_coil("fault_alarm", True)

    def inject_emergency_stop(self):
        """
        Simulate emergency stop pressed.
        - E-stop active
        - All motors stopped
        - Fault alarm
        """
        logger.info("Injecting EMERGENCY STOP")
        self.write_coil("e_stop", True)
        self.write_coil("motor_running", False)
        self.write_coil("conveyor_running", False)
        self.write_register("error_code", self.ERROR_CODES["emergency_stop"])
        self.write_coil("fault_alarm", True)

    def inject_sensor_failure(self):
        """
        Simulate sensor communication failure.
        - Both sensors show as disconnected (False)
        - Sets sensor failure error
        """
        logger.info("Injecting SENSOR FAILURE")
        self.write_coil("sensor_1", False)
        self.write_coil("sensor_2", False)
        self.write_register("error_code", self.ERROR_CODES["sensor_failure"])
        self.write_coil("fault_alarm", True)

    def clear_all_faults(self):
        """
        Clear all fault conditions and return to normal.
        """
        logger.info("Clearing all faults")
        self.write_coil("fault_alarm", False)
        self.write_coil("e_stop", False)
        self.write_register("error_code", 0)
        self.write_register("temperature", 650)  # Normal 65C
        self.write_register("pressure", 100)  # Normal 100 PSI
        self.write_register("motor_current", 25)  # Normal 2.5A

    def set_normal_operation(self):
        """
        Set Factory I/O to normal running state.
        """
        logger.info("Setting NORMAL operation state")
        self.clear_all_faults()
        self.write_coil("motor_running", True)
        self.write_coil("conveyor_running", True)
        self.write_register("motor_speed", 50)
        self.write_register("conveyor_speed", 50)
