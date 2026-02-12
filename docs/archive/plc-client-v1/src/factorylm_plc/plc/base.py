"""
Base PLC Client Interface

Defines the abstract interface that all PLC providers must implement.
This ensures consistent behavior across Micro820, mock, and future PLC types.
"""

from abc import ABC, abstractmethod
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..models import MachineState


class BasePLCClient(ABC):
    """
    Abstract base class for all PLC provider clients.

    All PLC clients (Micro820, Mock, future types) must inherit from this class
    and implement all abstract methods. This ensures a consistent interface
    for the factory function and downstream consumers.

    Example:
        >>> class MyPLCClient(BasePLCClient):
        ...     def connect(self) -> bool:
        ...         # Implementation
        ...         pass
        ...     # implement other abstract methods...
    """

    @abstractmethod
    def connect(self) -> bool:
        """
        Connect to the PLC.

        Returns:
            bool: True if connection successful, False otherwise

        Raises:
            ConnectionError: If connection fails with error details
        """
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """
        Disconnect from the PLC.

        Should be safe to call even if not connected.
        """
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """
        Check if currently connected to the PLC.

        Returns:
            bool: True if connected, False otherwise
        """
        pass

    @abstractmethod
    def read_state(self) -> Optional["MachineState"]:
        """
        Read current machine state from the PLC.

        This is the primary method for reading all sensor data at once.
        Returns a standardized MachineState object.

        Returns:
            MachineState: Current machine state with all sensor values,
                         or None if read fails

        Raises:
            ConnectionError: If not connected to PLC
            TimeoutError: If read times out
        """
        pass

    @abstractmethod
    def write_register(self, address: int, value: int) -> bool:
        """
        Write a value to a holding register.

        Args:
            address: Register address to write to
            value: Integer value to write (0-65535 for 16-bit register)

        Returns:
            bool: True if write successful, False otherwise

        Raises:
            ConnectionError: If not connected to PLC
            ValueError: If address or value is invalid
        """
        pass

    @abstractmethod
    def write_coil(self, address: int, value: bool) -> bool:
        """
        Write a value to a coil (discrete output).

        Args:
            address: Coil address to write to
            value: Boolean value (True/False, On/Off)

        Returns:
            bool: True if write successful, False otherwise

        Raises:
            ConnectionError: If not connected to PLC
            ValueError: If address is invalid
        """
        pass

    def __enter__(self) -> "BasePLCClient":
        """Context manager entry - connect to PLC."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - disconnect from PLC."""
        self.disconnect()

    def __repr__(self) -> str:
        """Return string representation of the client."""
        return f"{self.__class__.__name__}(connected={self.is_connected()})"
