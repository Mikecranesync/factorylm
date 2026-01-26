"""
Modbus TCP Client Wrapper

Provides a wrapper around pymodbus with retry logic, timeout handling,
and logging for industrial PLC communication.
"""

import logging
from typing import List, Optional
from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException

logger = logging.getLogger(__name__)


class ModbusTCPClient:
    """
    Modbus TCP client wrapper with retry logic and error handling.

    Wraps pymodbus ModbusTcpClient with:
    - Connection pooling (reuses connections)
    - Retry logic (configurable attempts)
    - Timeout handling
    - Logging of all reads/writes

    Args:
        host: IP address of Modbus TCP server
        port: TCP port (default 502)
        timeout: Connection/read timeout in seconds (default 5)
        retries: Number of retry attempts on failure (default 3)
    """

    def __init__(
        self,
        host: str,
        port: int = 502,
        timeout: int = 5,
        retries: int = 3
    ):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.retries = retries
        self._client: Optional[ModbusTcpClient] = None

    def connect(self) -> bool:
        """
        Connect to Modbus TCP server.

        Returns:
            bool: True if connection successful

        Raises:
            ConnectionError: If connection fails after retries
        """
        if self._client is not None and self._client.connected:
            return True

        self._client = ModbusTcpClient(
            host=self.host,
            port=self.port,
            timeout=self.timeout
        )

        for attempt in range(1, self.retries + 1):
            try:
                if self._client.connect():
                    logger.info(f"Connected to Modbus server at {self.host}:{self.port}")
                    return True
            except Exception as e:
                logger.warning(f"Connection attempt {attempt}/{self.retries} failed: {e}")

            if attempt < self.retries:
                import time
                time.sleep(1)  # Wait before retry

        raise ConnectionError(
            f"Failed to connect to {self.host}:{self.port} after {self.retries} attempts"
        )

    def disconnect(self) -> None:
        """Disconnect from Modbus TCP server."""
        if self._client is not None:
            self._client.close()
            logger.info(f"Disconnected from {self.host}:{self.port}")
            self._client = None

    def is_connected(self) -> bool:
        """Check if connected to Modbus server."""
        return self._client is not None and self._client.connected

    def read_registers(
        self,
        start_addr: int,
        count: int,
        unit: int = 1
    ) -> List[int]:
        """
        Read multiple holding registers.

        Args:
            start_addr: Starting register address
            count: Number of registers to read
            unit: Modbus unit/slave ID (default 1)

        Returns:
            List of register values

        Raises:
            ConnectionError: If not connected
            ModbusException: If read fails
        """
        if not self.is_connected():
            raise ConnectionError("Not connected to Modbus server")

        for attempt in range(1, self.retries + 1):
            try:
                result = self._client.read_holding_registers(
                    address=start_addr,
                    count=count,
                    slave=unit
                )

                if result.isError():
                    raise ModbusException(f"Modbus error: {result}")

                values = list(result.registers)
                logger.debug(
                    f"Read registers {start_addr}-{start_addr + count - 1}: {values}"
                )
                return values

            except ModbusException as e:
                logger.warning(
                    f"Read attempt {attempt}/{self.retries} failed: {e}"
                )
                if attempt == self.retries:
                    raise

        return []  # Should not reach here

    def read_coils(
        self,
        start_addr: int,
        count: int,
        unit: int = 1
    ) -> List[bool]:
        """
        Read multiple coils (discrete inputs).

        Args:
            start_addr: Starting coil address
            count: Number of coils to read
            unit: Modbus unit/slave ID (default 1)

        Returns:
            List of coil values (True/False)

        Raises:
            ConnectionError: If not connected
            ModbusException: If read fails
        """
        if not self.is_connected():
            raise ConnectionError("Not connected to Modbus server")

        for attempt in range(1, self.retries + 1):
            try:
                result = self._client.read_coils(
                    address=start_addr,
                    count=count,
                    slave=unit
                )

                if result.isError():
                    raise ModbusException(f"Modbus error: {result}")

                values = list(result.bits[:count])
                logger.debug(
                    f"Read coils {start_addr}-{start_addr + count - 1}: {values}"
                )
                return values

            except ModbusException as e:
                logger.warning(
                    f"Read coils attempt {attempt}/{self.retries} failed: {e}"
                )
                if attempt == self.retries:
                    raise

        return []  # Should not reach here

    def write_register(
        self,
        address: int,
        value: int,
        unit: int = 1
    ) -> bool:
        """
        Write a value to a holding register.

        Args:
            address: Register address
            value: Value to write (0-65535)
            unit: Modbus unit/slave ID (default 1)

        Returns:
            bool: True if write successful

        Raises:
            ConnectionError: If not connected
            ValueError: If value out of range
        """
        if not self.is_connected():
            raise ConnectionError("Not connected to Modbus server")

        if not 0 <= value <= 65535:
            raise ValueError(f"Register value must be 0-65535, got {value}")

        for attempt in range(1, self.retries + 1):
            try:
                result = self._client.write_register(
                    address=address,
                    value=value,
                    slave=unit
                )

                if result.isError():
                    raise ModbusException(f"Modbus error: {result}")

                logger.info(f"Wrote register {address} = {value}")
                return True

            except ModbusException as e:
                logger.warning(
                    f"Write attempt {attempt}/{self.retries} failed: {e}"
                )
                if attempt == self.retries:
                    raise

        return False

    def write_coil(
        self,
        address: int,
        value: bool,
        unit: int = 1
    ) -> bool:
        """
        Write a value to a coil.

        Args:
            address: Coil address
            value: Boolean value to write
            unit: Modbus unit/slave ID (default 1)

        Returns:
            bool: True if write successful

        Raises:
            ConnectionError: If not connected
        """
        if not self.is_connected():
            raise ConnectionError("Not connected to Modbus server")

        for attempt in range(1, self.retries + 1):
            try:
                result = self._client.write_coil(
                    address=address,
                    value=value,
                    slave=unit
                )

                if result.isError():
                    raise ModbusException(f"Modbus error: {result}")

                logger.info(f"Wrote coil {address} = {value}")
                return True

            except ModbusException as e:
                logger.warning(
                    f"Write coil attempt {attempt}/{self.retries} failed: {e}"
                )
                if attempt == self.retries:
                    raise

        return False

    def __enter__(self) -> "ModbusTCPClient":
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.disconnect()
