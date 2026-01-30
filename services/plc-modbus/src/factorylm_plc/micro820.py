"""
Allen-Bradley Micro 820 PLC client implementation.

Provides generic Micro 820 support with configurable register mapping.
"""

from datetime import datetime
from typing import List, Dict, Optional

from .modbus_client import ModbusTCPClient
from .models import MachineState


class Micro820PLC(ModbusTCPClient):
    """
    Allen-Bradley Micro 820 PLC client.

    Extends ModbusTCPClient with Micro 820-specific register mapping
    and state reading capabilities.
    """

    # Default register addresses (override in subclass for specific configs)
    REGISTERS: Dict[str, int] = {
        "motor_speed": 100,
        "motor_current": 101,
        "temperature": 102,
        "pressure": 103,
    }

    # Default coil addresses
    COILS: Dict[str, int] = {
        "motor_running": 0,
        "motor_stopped": 1,
        "fault_alarm": 2,
    }

    # Scale factors for raw register values
    SCALE_FACTORS: Dict[str, float] = {
        "motor_current": 10.0,  # Divide raw value by 10
        "temperature": 10.0,    # Divide raw value by 10
    }

    def __init__(
        self,
        host: str,
        port: int = 502,
        timeout: float = 5.0,
        retries: int = 3,
        unit_id: int = 1,
    ):
        """
        Initialize Micro820PLC client.

        Args:
            host: PLC IP address or hostname.
            port: Modbus TCP port (default 502).
            timeout: Connection/read timeout in seconds.
            retries: Number of retry attempts for failed operations.
            unit_id: Modbus unit/slave ID (default 1).
        """
        super().__init__(host, port, timeout, retries, unit_id)

    def _get_register_address(self, name: str) -> int:
        """Get register address by name."""
        if name not in self.REGISTERS:
            raise ValueError(f"Unknown register: {name}")
        return self.REGISTERS[name]

    def _get_coil_address(self, name: str) -> int:
        """Get coil address by name."""
        if name not in self.COILS:
            raise ValueError(f"Unknown coil: {name}")
        return self.COILS[name]

    def _apply_scale_factor(self, name: str, raw_value: int) -> float:
        """Apply scale factor to raw register value."""
        if name in self.SCALE_FACTORS:
            return raw_value / self.SCALE_FACTORS[name]
        return float(raw_value)

    def read_register_by_name(self, name: str) -> float:
        """
        Read a single register by name.

        Args:
            name: Register name (e.g., "motor_speed", "temperature").

        Returns:
            float: Scaled register value.
        """
        address = self._get_register_address(name)
        values = self.read_holding_registers(address, 1)
        return self._apply_scale_factor(name, values[0])

    def read_coil_by_name(self, name: str) -> bool:
        """
        Read a single coil by name.

        Args:
            name: Coil name (e.g., "motor_running", "fault_alarm").

        Returns:
            bool: Coil value.
        """
        address = self._get_coil_address(name)
        values = self.read_coils(address, 1)
        return values[0]

    def write_register_by_name(self, name: str, value: float) -> bool:
        """
        Write a value to a register by name.

        Args:
            name: Register name.
            value: Value to write (will be scaled appropriately).

        Returns:
            bool: True if write successful.
        """
        address = self._get_register_address(name)
        # Apply inverse scale factor
        if name in self.SCALE_FACTORS:
            raw_value = int(value * self.SCALE_FACTORS[name])
        else:
            raw_value = int(value)
        return self.write_register(address, raw_value)

    def write_coil_by_name(self, name: str, value: bool) -> bool:
        """
        Write a value to a coil by name.

        Args:
            name: Coil name.
            value: Boolean value to write.

        Returns:
            bool: True if write successful.
        """
        address = self._get_coil_address(name)
        return self.write_coil(address, value)

    def read_all_registers(self) -> Dict[str, float]:
        """
        Read all configured registers.

        Returns:
            Dict[str, float]: Register name to scaled value mapping.
        """
        result = {}
        # Find contiguous block of registers
        addresses = sorted(self.REGISTERS.values())
        if not addresses:
            return result

        start_address = addresses[0]
        count = addresses[-1] - start_address + 1

        # Read all registers in one call
        values = self.read_holding_registers(start_address, count)

        # Map values to names
        for name, address in self.REGISTERS.items():
            index = address - start_address
            if 0 <= index < len(values):
                result[name] = self._apply_scale_factor(name, values[index])

        return result

    def read_all_coils(self) -> Dict[str, bool]:
        """
        Read all configured coils.

        Returns:
            Dict[str, bool]: Coil name to value mapping.
        """
        result = {}
        # Find contiguous block of coils
        addresses = sorted(self.COILS.values())
        if not addresses:
            return result

        start_address = addresses[0]
        count = addresses[-1] - start_address + 1

        # Read all coils in one call
        values = self.read_coils(start_address, count)

        # Map values to names
        for name, address in self.COILS.items():
            index = address - start_address
            if 0 <= index < len(values):
                result[name] = values[index]

        return result

    def read_state(self) -> MachineState:
        """
        Read the current machine state from the PLC.

        Returns:
            MachineState: Current state of the machine.
        """
        # Read all registers and coils
        registers = self.read_all_registers()
        coils = self.read_all_coils()

        return MachineState(
            motor_running=coils.get("motor_running", False),
            motor_speed=int(registers.get("motor_speed", 0)),
            motor_current=registers.get("motor_current", 0.0),
            temperature=registers.get("temperature", 0.0),
            pressure=int(registers.get("pressure", 0)),
            fault_active=coils.get("fault_alarm", False),
            timestamp=datetime.now(),
        )
