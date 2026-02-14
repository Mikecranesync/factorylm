"""
Mock PLC Client

In-memory PLC simulator for testing without real hardware.
Simulates realistic machine behavior.
"""

import logging
import time
from typing import Optional, Dict, Any

from ..models import MachineState
from .base import BasePLCClient

logger = logging.getLogger(__name__)


class MockPLC(BasePLCClient):
    """
    Mock PLC for testing without real hardware.

    Simulates realistic machine behavior:
    - Temperature increases when motor is running
    - Motor current varies with speed
    - Pressure stays relatively constant
    - No network calls - all in-memory

    This is perfect for unit testing and development without a real PLC.
    """

    def __init__(self):
        # Simulated register values
        self._registers: Dict[int, int] = {
            100: 0,    # motor_speed
            101: 0,    # motor_current
            102: 250,  # temperature (25.0°C * 10)
            103: 100,  # pressure
        }

        # Simulated coil values
        self._coils: Dict[int, bool] = {
            0: False,  # motor_running
            1: True,   # motor_stopped
            2: False,  # fault_alarm
        }

        self._connected = False
        self._last_update = time.time()

    def connect(self) -> bool:
        """
        Simulate connection to PLC.

        Always succeeds for mock PLC.
        """
        self._connected = True
        self._last_update = time.time()
        logger.info("Connected to MockPLC")
        return True

    def disconnect(self) -> None:
        """Simulate disconnection."""
        self._connected = False
        logger.info("Disconnected from MockPLC")

    def is_connected(self) -> bool:
        """Check simulated connection status."""
        return self._connected

    def _simulate_behavior(self) -> None:
        """
        Simulate realistic machine behavior over time.

        Called before each read to update simulated values.
        """
        now = time.time()
        elapsed = now - self._last_update
        self._last_update = now

        # If motor is running, simulate behavior
        if self._coils[0]:  # motor_running
            # Temperature rises slowly when motor is running
            current_temp = self._registers[102]
            temp_rise = int(elapsed * 5)  # 0.5°C per second
            self._registers[102] = min(current_temp + temp_rise, 800)  # Max 80°C

            # Current varies with speed
            speed = self._registers[100]
            base_current = 5 + (speed // 20)  # Base current + speed factor
            self._registers[101] = base_current

        else:
            # Temperature falls slowly when motor is stopped
            current_temp = self._registers[102]
            temp_fall = int(elapsed * 2)  # 0.2°C per second
            self._registers[102] = max(current_temp - temp_fall, 200)  # Min 20°C

            # No current when stopped
            self._registers[101] = 0

    def read_state(self) -> Optional[MachineState]:
        """
        Read simulated machine state.

        Returns:
            MachineState: Simulated machine state
        """
        if not self._connected:
            logger.error("Cannot read state: MockPLC not connected")
            return None

        # Update simulation
        self._simulate_behavior()

        state = MachineState(
            motor_speed=self._registers[100],
            motor_current=self._registers[101],
            temperature=self._registers[102] / 10.0,
            pressure=self._registers[103],
            motor_running=self._coils[0],
            motor_stopped=self._coils[1],
            fault_alarm=self._coils[2],
            timestamp=time.time(),
            raw_registers={
                "registers": dict(self._registers),
                "coils": dict(self._coils)
            }
        )

        logger.debug(f"MockPLC read state: {state}")
        return state

    def write_register(self, address: int, value: int) -> bool:
        """
        Write to simulated register.

        Args:
            address: Register address
            value: Value to write (0-65535)

        Returns:
            bool: True if write successful
        """
        if not self._connected:
            raise ConnectionError("MockPLC not connected")

        if not 0 <= value <= 65535:
            raise ValueError(f"Register value must be 0-65535, got {value}")

        self._registers[address] = value
        logger.info(f"MockPLC write register {address} = {value}")
        return True

    def write_coil(self, address: int, value: bool) -> bool:
        """
        Write to simulated coil.

        Args:
            address: Coil address
            value: Boolean value

        Returns:
            bool: True if write successful
        """
        if not self._connected:
            raise ConnectionError("MockPLC not connected")

        self._coils[address] = value

        # Handle motor running/stopped logic
        if address == 0 and value:  # motor_running = True
            self._coils[1] = False  # motor_stopped = False
        elif address == 1 and value:  # motor_stopped = True
            self._coils[0] = False  # motor_running = False

        logger.info(f"MockPLC write coil {address} = {value}")
        return True

    def set_motor_speed(self, speed: int) -> bool:
        """
        Convenience method to set simulated motor speed.

        Args:
            speed: Motor speed in RPM

        Returns:
            bool: True if successful
        """
        return self.write_register(100, speed)

    def start_motor(self) -> bool:
        """
        Convenience method to start simulated motor.

        Returns:
            bool: True if successful
        """
        return self.write_coil(0, True)

    def stop_motor(self) -> bool:
        """
        Convenience method to stop simulated motor.

        Returns:
            bool: True if successful
        """
        return self.write_coil(1, True)

    def trigger_fault(self) -> bool:
        """
        Trigger a simulated fault alarm.

        Returns:
            bool: True if successful
        """
        return self.write_coil(2, True)

    def clear_fault(self) -> bool:
        """
        Clear simulated fault alarm.

        Returns:
            bool: True if successful
        """
        return self.write_coil(2, False)

    def reset(self) -> None:
        """Reset MockPLC to initial state."""
        self._registers = {
            100: 0,
            101: 0,
            102: 250,
            103: 100,
        }
        self._coils = {
            0: False,
            1: True,
            2: False,
        }
        self._last_update = time.time()
        logger.info("MockPLC reset to initial state")

    def __repr__(self) -> str:
        """String representation."""
        return f"MockPLC(connected={self._connected})"
