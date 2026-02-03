"""
Modbus TCP client wrapper using pymodbus.

Provides low-level Modbus communication with timeout and retry handling.
"""

import logging
from typing import Optional, List

from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException

from .base import BasePLCClient
from .models import MachineState

logger = logging.getLogger(__name__)


class ModbusTCPClient(BasePLCClient):
    """
    Low-level Modbus TCP client wrapper using pymodbus.

    Provides read/write operations for holding registers and coils with
    proper error handling and connection management.
    """

    DEFAULT_PORT = 502
    DEFAULT_TIMEOUT = 5.0
    DEFAULT_RETRIES = 3

    def __init__(
        self,
        host: str,
        port: int = DEFAULT_PORT,
        timeout: float = DEFAULT_TIMEOUT,
        retries: int = DEFAULT_RETRIES,
        unit_id: int = 1,
    ):
        """
        Initialize ModbusTCPClient.

        Args:
            host: PLC IP address or hostname.
            port: Modbus TCP port (default 502).
            timeout: Connection/read timeout in seconds.
            retries: Number of retry attempts for failed operations.
            unit_id: Modbus unit/slave ID (default 1).
        """
        self.host = host
        self.port = port
        self.timeout = timeout
        self.retries = retries
        self.unit_id = unit_id
        self._client: Optional[ModbusTcpClient] = None
        self._connected = False

    def connect(self) -> bool:
        """
        Establish connection to the PLC via Modbus TCP.

        Returns:
            bool: True if connection successful, False otherwise.
        """
        try:
            self._client = ModbusTcpClient(
                host=self.host,
                port=self.port,
                timeout=self.timeout,
                retries=self.retries,
            )
            self._connected = self._client.connect()
            if self._connected:
                logger.info(f"Connected to PLC at {self.host}:{self.port}")
            else:
                logger.warning(f"Failed to connect to PLC at {self.host}:{self.port}")
            return self._connected
        except Exception as e:
            logger.error(f"Connection error: {e}")
            self._connected = False
            return False

    def disconnect(self) -> None:
        """Close the Modbus TCP connection."""
        if self._client:
            self._client.close()
            self._connected = False
            logger.info(f"Disconnected from PLC at {self.host}:{self.port}")

    def is_connected(self) -> bool:
        """
        Check if currently connected to the PLC.

        Returns:
            bool: True if connected, False otherwise.
        """
        if not self._client:
            return False
        return self._connected and self._client.connected

    def _ensure_connected(self) -> None:
        """Raise ConnectionError if not connected."""
        if not self.is_connected():
            raise ConnectionError(f"Not connected to PLC at {self.host}:{self.port}")

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
        self._ensure_connected()

        try:
            result = self._client.read_holding_registers(
                address=address,
                count=count,
                device_id=self.unit_id,
            )
            if result.isError():
                raise IOError(f"Failed to read registers at {address}: {result}")
            return list(result.registers)
        except ModbusException as e:
            logger.error(f"Modbus error reading registers at {address}: {e}")
            raise IOError(f"Modbus error: {e}") from e

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
        self._ensure_connected()

        try:
            result = self._client.read_coils(
                address=address,
                count=count,
                device_id=self.unit_id,
            )
            if result.isError():
                raise IOError(f"Failed to read coils at {address}: {result}")
            return list(result.bits[:count])
        except ModbusException as e:
            logger.error(f"Modbus error reading coils at {address}: {e}")
            raise IOError(f"Modbus error: {e}") from e

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
        self._ensure_connected()

        try:
            result = self._client.write_register(
                address=address,
                value=value,
                device_id=self.unit_id,
            )
            if result.isError():
                logger.error(f"Failed to write register at {address}: {result}")
                return False
            return True
        except ModbusException as e:
            logger.error(f"Modbus error writing register at {address}: {e}")
            raise IOError(f"Modbus error: {e}") from e

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
        self._ensure_connected()

        try:
            result = self._client.write_coil(
                address=address,
                value=value,
                device_id=self.unit_id,
            )
            if result.isError():
                logger.error(f"Failed to write coil at {address}: {result}")
                return False
            return True
        except ModbusException as e:
            logger.error(f"Modbus error writing coil at {address}: {e}")
            raise IOError(f"Modbus error: {e}") from e

    def read_state(self) -> MachineState:
        """
        Read the current machine state from the PLC.

        Note: This is a basic implementation. Subclasses should override
        with proper register mapping.

        Returns:
            MachineState: Current state of the machine.
        """
        raise NotImplementedError(
            "ModbusTCPClient is a low-level client. "
            "Use Micro820PLC or FactoryIOMicro820 for state reading."
        )
