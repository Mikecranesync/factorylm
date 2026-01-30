"""
Abstract base class for PLC clients.

Defines the interface that all PLC client implementations must follow.
"""

from abc import ABC, abstractmethod
from typing import Optional, List

from .models import MachineState


class BasePLCClient(ABC):
    """
    Abstract base class for PLC clients.

    All PLC client implementations (Mock, Modbus, etc.) must extend this class
    and implement all abstract methods.
    """

    @abstractmethod
    def connect(self) -> bool:
        """
        Establish connection to the PLC.

        Returns:
            bool: True if connection successful, False otherwise.
        """
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Close the connection to the PLC."""
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """
        Check if currently connected to the PLC.

        Returns:
            bool: True if connected, False otherwise.
        """
        pass

    @abstractmethod
    def read_state(self) -> MachineState:
        """
        Read the current machine state from the PLC.

        Returns:
            MachineState: Current state of the machine.

        Raises:
            ConnectionError: If not connected to PLC.
            IOError: If read operation fails.
        """
        pass

    @abstractmethod
    def read_holding_registers(self, address: int, count: int) -> List[int]:
        """
        Read holding registers from the PLC.

        Args:
            address: Starting register address.
            count: Number of registers to read.

        Returns:
            List[int]: Values read from registers.

        Raises:
            ConnectionError: If not connected to PLC.
            IOError: If read operation fails.
        """
        pass

    @abstractmethod
    def read_coils(self, address: int, count: int) -> List[bool]:
        """
        Read coils (boolean values) from the PLC.

        Args:
            address: Starting coil address.
            count: Number of coils to read.

        Returns:
            List[bool]: Boolean values read from coils.

        Raises:
            ConnectionError: If not connected to PLC.
            IOError: If read operation fails.
        """
        pass

    @abstractmethod
    def write_register(self, address: int, value: int) -> bool:
        """
        Write a value to a holding register.

        Args:
            address: Register address to write to.
            value: Value to write.

        Returns:
            bool: True if write successful, False otherwise.

        Raises:
            ConnectionError: If not connected to PLC.
            IOError: If write operation fails.
        """
        pass

    @abstractmethod
    def write_coil(self, address: int, value: bool) -> bool:
        """
        Write a value to a coil.

        Args:
            address: Coil address to write to.
            value: Boolean value to write.

        Returns:
            bool: True if write successful, False otherwise.

        Raises:
            ConnectionError: If not connected to PLC.
            IOError: If write operation fails.
        """
        pass

    def __enter__(self):
        """Context manager entry - connect to PLC."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - disconnect from PLC."""
        self.disconnect()
        return False
