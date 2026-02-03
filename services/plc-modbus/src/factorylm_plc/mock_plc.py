"""
Mock PLC implementation for testing without hardware.

Simulates realistic machine behavior including:
- Temperature increases when motor runs
- Current changes with speed
- Sensor toggling
- Error conditions
"""

import random
from datetime import datetime
from typing import List, Dict, Any

from .base import BasePLCClient
from .models import FactoryState


class MockPLC(BasePLCClient):
    """
    Mock PLC for testing without real hardware.

    Simulates Factory I/O + Micro 820 behavior with realistic values
    and state changes.
    """

    # Holding register addresses (matching Micro 820 config)
    REGISTER_MOTOR_SPEED = 100
    REGISTER_MOTOR_CURRENT = 101
    REGISTER_TEMPERATURE = 102
    REGISTER_PRESSURE = 103
    REGISTER_CONVEYOR_SPEED = 104
    REGISTER_ERROR_CODE = 105

    # Coil addresses
    COIL_MOTOR_RUNNING = 0
    COIL_MOTOR_STOPPED = 1
    COIL_FAULT_ALARM = 2
    COIL_CONVEYOR_RUNNING = 3
    COIL_SENSOR_1 = 4
    COIL_SENSOR_2 = 5
    COIL_E_STOP = 6

    def __init__(self, initial_state: Dict[str, Any] = None):
        """
        Initialize MockPLC with optional initial state.

        Args:
            initial_state: Optional dict to override default register/coil values.
        """
        self._connected = False

        # Initialize registers with realistic defaults
        # Values stored as raw integers (before scale factor applied)
        self._registers: Dict[int, int] = {
            self.REGISTER_MOTOR_SPEED: 0,       # 0%
            self.REGISTER_MOTOR_CURRENT: 0,     # 0.0A (raw: 0)
            self.REGISTER_TEMPERATURE: 250,     # 25.0C (raw: 250)
            self.REGISTER_PRESSURE: 100,        # 100 PSI
            self.REGISTER_CONVEYOR_SPEED: 0,    # 0%
            self.REGISTER_ERROR_CODE: 0,        # No error
        }

        # Initialize coils (boolean states)
        self._coils: Dict[int, bool] = {
            self.COIL_MOTOR_RUNNING: False,
            self.COIL_MOTOR_STOPPED: True,
            self.COIL_FAULT_ALARM: False,
            self.COIL_CONVEYOR_RUNNING: False,
            self.COIL_SENSOR_1: False,
            self.COIL_SENSOR_2: False,
            self.COIL_E_STOP: False,
        }

        # Apply initial state if provided
        if initial_state:
            self._apply_initial_state(initial_state)

        # Scene name for Factory I/O
        self.scene_name = "sorting_station"

    def _apply_initial_state(self, state: Dict[str, Any]) -> None:
        """Apply initial state values to registers and coils."""
        # Map friendly names to register addresses
        register_map = {
            "motor_speed": self.REGISTER_MOTOR_SPEED,
            "motor_current": self.REGISTER_MOTOR_CURRENT,
            "temperature": self.REGISTER_TEMPERATURE,
            "pressure": self.REGISTER_PRESSURE,
            "conveyor_speed": self.REGISTER_CONVEYOR_SPEED,
            "error_code": self.REGISTER_ERROR_CODE,
        }

        coil_map = {
            "motor_running": self.COIL_MOTOR_RUNNING,
            "motor_stopped": self.COIL_MOTOR_STOPPED,
            "fault_alarm": self.COIL_FAULT_ALARM,
            "conveyor_running": self.COIL_CONVEYOR_RUNNING,
            "sensor_1_active": self.COIL_SENSOR_1,
            "sensor_2_active": self.COIL_SENSOR_2,
            "e_stop_active": self.COIL_E_STOP,
        }

        for key, value in state.items():
            if key in register_map:
                self._registers[register_map[key]] = value
            elif key in coil_map:
                self._coils[coil_map[key]] = value

    def connect(self) -> bool:
        """Simulate connection (always succeeds for mock)."""
        self._connected = True
        return True

    def disconnect(self) -> None:
        """Simulate disconnection."""
        self._connected = False

    def is_connected(self) -> bool:
        """Check simulated connection state."""
        return self._connected

    def _ensure_connected(self) -> None:
        """Raise ConnectionError if not connected."""
        if not self._connected:
            raise ConnectionError("MockPLC is not connected")

    def read_holding_registers(self, address: int, count: int) -> List[int]:
        """
        Read simulated holding registers.

        Args:
            address: Starting register address.
            count: Number of registers to read.

        Returns:
            List[int]: Simulated register values.
        """
        self._ensure_connected()
        self._simulate_behavior()

        values = []
        for i in range(count):
            addr = address + i
            values.append(self._registers.get(addr, 0))
        return values

    def read_coils(self, address: int, count: int) -> List[bool]:
        """
        Read simulated coils.

        Args:
            address: Starting coil address.
            count: Number of coils to read.

        Returns:
            List[bool]: Simulated coil values.
        """
        self._ensure_connected()

        values = []
        for i in range(count):
            addr = address + i
            values.append(self._coils.get(addr, False))
        return values

    def write_register(self, address: int, value: int) -> bool:
        """
        Write to a simulated holding register.

        Args:
            address: Register address.
            value: Value to write.

        Returns:
            bool: Always True for mock.
        """
        self._ensure_connected()
        self._registers[address] = value

        # Update motor_stopped coil when speed changes
        if address == self.REGISTER_MOTOR_SPEED:
            self._coils[self.COIL_MOTOR_STOPPED] = (value == 0)

        return True

    def write_coil(self, address: int, value: bool) -> bool:
        """
        Write to a simulated coil.

        Args:
            address: Coil address.
            value: Boolean value to write.

        Returns:
            bool: Always True for mock.
        """
        self._ensure_connected()
        self._coils[address] = value

        # Keep motor_running and motor_stopped in sync
        if address == self.COIL_MOTOR_RUNNING:
            self._coils[self.COIL_MOTOR_STOPPED] = not value
            if not value:
                self._registers[self.REGISTER_MOTOR_SPEED] = 0
                self._registers[self.REGISTER_MOTOR_CURRENT] = 0
        elif address == self.COIL_MOTOR_STOPPED:
            self._coils[self.COIL_MOTOR_RUNNING] = not value

        return True

    def _simulate_behavior(self) -> None:
        """
        Simulate realistic machine behavior.

        Called on each read to update state based on running conditions.
        """
        motor_running = self._coils[self.COIL_MOTOR_RUNNING]
        speed = self._registers[self.REGISTER_MOTOR_SPEED]
        temp = self._registers[self.REGISTER_TEMPERATURE]

        if motor_running and speed > 0:
            # Current increases with speed (scaled by 10)
            base_current = int(speed * 0.5)  # 0.5A per % speed
            noise = random.randint(-5, 5)
            self._registers[self.REGISTER_MOTOR_CURRENT] = max(0, base_current + noise)

            # Temperature slowly increases when running (max 80C = 800 raw)
            if temp < 800:
                self._registers[self.REGISTER_TEMPERATURE] = min(800, temp + random.randint(1, 3))
        else:
            # Motor off - current drops, temp cools
            if temp > 250:  # Cool back to 25C
                self._registers[self.REGISTER_TEMPERATURE] = max(250, temp - random.randint(1, 5))

        # Randomly toggle sensors to simulate parts moving
        if self._coils[self.COIL_CONVEYOR_RUNNING]:
            if random.random() < 0.1:  # 10% chance to toggle
                self._coils[self.COIL_SENSOR_1] = random.choice([True, False])
            if random.random() < 0.1:
                self._coils[self.COIL_SENSOR_2] = random.choice([True, False])

    def read_state(self) -> FactoryState:
        """
        Read the complete factory state.

        Returns:
            FactoryState: Current simulated state with all values.
        """
        self._ensure_connected()
        self._simulate_behavior()

        # Read all registers
        registers = self.read_holding_registers(100, 6)
        coils = self.read_coils(0, 7)

        # Apply scale factors
        motor_current = registers[1] / 10.0  # Scale by 10
        temperature = registers[2] / 10.0    # Scale by 10

        return FactoryState(
            # Motor state
            motor_running=coils[0],
            motor_speed=registers[0],
            motor_current=motor_current,

            # Environmental
            temperature=temperature,
            pressure=registers[3],

            # Fault
            fault_active=coils[2],

            # Conveyor
            conveyor_speed=registers[4],
            conveyor_running=coils[3],

            # Sensors
            sensor_1_active=coils[4],
            sensor_2_active=coils[5],

            # Safety
            e_stop_active=coils[6],

            # Error
            error_code=registers[5],

            # Metadata
            timestamp=datetime.now(),
            scene_name=self.scene_name,
        )

    def start_motor(self, speed: int = 50) -> bool:
        """
        Helper method to start the motor.

        Args:
            speed: Motor speed percentage (0-100).

        Returns:
            bool: True on success.
        """
        self.write_coil(self.COIL_MOTOR_RUNNING, True)
        self.write_register(self.REGISTER_MOTOR_SPEED, min(100, max(0, speed)))
        return True

    def stop_motor(self) -> bool:
        """
        Helper method to stop the motor.

        Returns:
            bool: True on success.
        """
        self.write_coil(self.COIL_MOTOR_RUNNING, False)
        return True

    def start_conveyor(self, speed: int = 50) -> bool:
        """
        Helper method to start the conveyor.

        Args:
            speed: Conveyor speed percentage (0-100).

        Returns:
            bool: True on success.
        """
        self.write_coil(self.COIL_CONVEYOR_RUNNING, True)
        self.write_register(self.REGISTER_CONVEYOR_SPEED, min(100, max(0, speed)))
        return True

    def stop_conveyor(self) -> bool:
        """
        Helper method to stop the conveyor.

        Returns:
            bool: True on success.
        """
        self.write_coil(self.COIL_CONVEYOR_RUNNING, False)
        self.write_register(self.REGISTER_CONVEYOR_SPEED, 0)
        return True

    def trigger_error(self, error_code: int) -> None:
        """
        Simulate an error condition.

        Args:
            error_code: Error code to set (1-5).
        """
        self.write_register(self.REGISTER_ERROR_CODE, error_code)
        if error_code > 0:
            self.write_coil(self.COIL_FAULT_ALARM, True)
        else:
            self.write_coil(self.COIL_FAULT_ALARM, False)

    def clear_error(self) -> None:
        """Clear any active error condition."""
        self.trigger_error(0)

    def trigger_estop(self) -> None:
        """Simulate emergency stop activation."""
        self.write_coil(self.COIL_E_STOP, True)
        self.stop_motor()
        self.stop_conveyor()

    def release_estop(self) -> None:
        """Release emergency stop."""
        self.write_coil(self.COIL_E_STOP, False)
