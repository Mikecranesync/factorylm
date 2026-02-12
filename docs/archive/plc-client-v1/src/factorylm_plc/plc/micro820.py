"""
Micro820 PLC Client

Implementation of BasePLCClient for Allen-Bradley Micro820 PLC
using Modbus TCP communication.
"""

import logging
import time
from typing import Optional

from ..models import MachineState
from ..modbus.client import ModbusTCPClient
from .base import BasePLCClient

logger = logging.getLogger(__name__)


class Micro820PLC(BasePLCClient):
    """
    Micro820 PLC client with hardcoded register mapping.

    Register Mapping (from CCW configuration):
        Holding Registers:
            100: motor_speed (RPM)
            101: motor_current (Amps)
            102: temperature (scaled 10x, divide by 10 for Celsius)
            103: pressure (PSI)

        Coils:
            0: motor_running
            1: motor_stopped
            2: fault_alarm

    Args:
        host: IP address of the Micro820 PLC
        port: Modbus TCP port (default 502)
        timeout: Connection timeout in seconds (default 5)
    """

    # Holding register addresses
    REG_MOTOR_SPEED = 100
    REG_MOTOR_CURRENT = 101
    REG_TEMPERATURE = 102
    REG_PRESSURE = 103

    # Coil addresses
    COIL_MOTOR_RUNNING = 0
    COIL_MOTOR_STOPPED = 1
    COIL_FAULT_ALARM = 2

    def __init__(self, host: str, port: int = 502, timeout: int = 5):
        self.host = host
        self.port = port
        self.timeout = timeout
        self._modbus = ModbusTCPClient(host, port, timeout)
        self._connected = False

    def connect(self) -> bool:
        """
        Connect to the Micro820 PLC via Modbus TCP.

        Returns:
            bool: True if connection successful
        """
        try:
            self._modbus.connect()
            self._connected = True
            logger.info(f"Connected to Micro820 at {self.host}:{self.port}")
            return True
        except ConnectionError as e:
            logger.error(f"Failed to connect to Micro820: {e}")
            self._connected = False
            raise

    def disconnect(self) -> None:
        """Disconnect from the Micro820 PLC."""
        self._modbus.disconnect()
        self._connected = False
        logger.info(f"Disconnected from Micro820 at {self.host}")

    def is_connected(self) -> bool:
        """Check if connected to the PLC."""
        return self._connected and self._modbus.is_connected()

    def read_state(self) -> Optional[MachineState]:
        """
        Read current machine state from the Micro820.

        Reads all registers and coils in a batch, then constructs
        a MachineState object with the values.

        Returns:
            MachineState: Current machine state, or None if read fails
        """
        if not self.is_connected():
            logger.error("Cannot read state: not connected")
            return None

        try:
            # Read 4 holding registers starting at address 100
            registers = self._modbus.read_registers(
                start_addr=self.REG_MOTOR_SPEED,
                count=4
            )

            # Read 3 coils starting at address 0
            coils = self._modbus.read_coils(
                start_addr=self.COIL_MOTOR_RUNNING,
                count=3
            )

            # Parse values
            motor_speed = registers[0]
            motor_current = registers[1]
            temperature = registers[2] / 10.0  # Scaled 10x
            pressure = registers[3]

            motor_running = coils[0]
            motor_stopped = coils[1]
            fault_alarm = coils[2]

            state = MachineState(
                motor_speed=motor_speed,
                motor_current=motor_current,
                temperature=temperature,
                pressure=pressure,
                motor_running=motor_running,
                motor_stopped=motor_stopped,
                fault_alarm=fault_alarm,
                timestamp=time.time(),
                raw_registers={
                    "registers": registers,
                    "coils": coils
                }
            )

            logger.debug(f"Read state from Micro820: {state}")
            return state

        except Exception as e:
            logger.error(f"Failed to read state from Micro820: {e}")
            return None

    def write_register(self, address: int, value: int) -> bool:
        """
        Write a value to a holding register.

        Args:
            address: Register address
            value: Value to write (0-65535)

        Returns:
            bool: True if write successful
        """
        if not self.is_connected():
            raise ConnectionError("Not connected to Micro820")

        return self._modbus.write_register(address, value)

    def write_coil(self, address: int, value: bool) -> bool:
        """
        Write a value to a coil.

        Args:
            address: Coil address
            value: Boolean value

        Returns:
            bool: True if write successful
        """
        if not self.is_connected():
            raise ConnectionError("Not connected to Micro820")

        return self._modbus.write_coil(address, value)

    def set_motor_speed(self, speed: int) -> bool:
        """
        Convenience method to set motor speed.

        Args:
            speed: Motor speed in RPM (0-65535)

        Returns:
            bool: True if write successful
        """
        return self.write_register(self.REG_MOTOR_SPEED, speed)

    def start_motor(self) -> bool:
        """
        Convenience method to start the motor.

        Returns:
            bool: True if write successful
        """
        return self.write_coil(self.COIL_MOTOR_RUNNING, True)

    def stop_motor(self) -> bool:
        """
        Convenience method to stop the motor.

        Returns:
            bool: True if write successful
        """
        return self.write_coil(self.COIL_MOTOR_STOPPED, True)

    def __repr__(self) -> str:
        """String representation."""
        return f"Micro820PLC(host={self.host}, connected={self.is_connected()})"
