"""PLC connection management service - singleton for managing Modbus TCP connection."""

import logging
from datetime import datetime
from typing import Optional, Dict, Any, List

from backend.config import settings

logger = logging.getLogger(__name__)


class PLCConnectionService:
    """
    Singleton service for managing PLC connection state.

    Wraps the Modbus TCP client and provides connection management,
    I/O reading, and coil writing capabilities.
    """

    _instance: Optional["PLCConnectionService"] = None

    # Coil name mappings — "From A to B" Factory I/O scene
    COIL_NAMES = {
        0: "Conveyor",      # PLC → Factory I/O: belt motor
        1: "Emitter",       # PLC → Factory I/O: item spawner
        2: "SensorStart",   # Factory I/O → PLC: entry sensor
        3: "SensorEnd",     # Factory I/O → PLC: exit sensor
        4: "RunCommand",    # Remote trigger (Telegram/API)
        5: "program_var_5",
        6: "program_var_6",
        7: "DI_00",  # 3-pos switch CENTER
        8: "DI_01",  # E-stop NO contact
        9: "DI_02",  # E-stop NC contact
        10: "DI_03", # 3-pos switch RIGHT
        11: "DI_04", # Left Pushbutton
        12: "DI_05",
        13: "DI_06",
        14: "DI_07",
        15: "DO_00", # 3-pos indicator LED
        16: "DO_01", # E-stop indicator LED
        17: "DO_03", # Auxiliary output
    }

    REGISTER_NAMES = {
        100: "ItemCount",
        101: "ConveyorHz",
        102: "MotorCurrentX10",
        103: "MotorTempX10",
        104: "VFDStatus",
        105: "ErrorCode",
    }

    # Writable coils: outputs (0,1), RunCommand (4), unused (5,6), physical outputs (15-17)
    # Coils 2,3 (SensorStart, SensorEnd) are Factory I/O inputs — read-only
    WRITABLE_COILS = [0, 1, 4, 5, 6, 15, 16, 17]

    def __new__(cls) -> "PLCConnectionService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._client = None
        self._ip: Optional[str] = None
        self._port: int = 502
        self._connected: bool = False
        self._last_seen: Optional[datetime] = None
        logger.info("PLCConnectionService initialized")

    @property
    def is_connected(self) -> bool:
        """Check if connected to PLC."""
        if self._client is None:
            return False
        try:
            return self._client.is_connected()
        except Exception:
            return False

    def connect(self, ip: str, port: int = 502) -> Dict[str, Any]:
        """
        Connect to PLC via Modbus TCP (or MockPLC if mock_mode is enabled).

        Args:
            ip: PLC IP address
            port: Modbus TCP port (default 502)

        Returns:
            Dict with success status and message
        """
        # Disconnect existing connection if any
        if self._client:
            try:
                self._client.disconnect()
            except Exception:
                pass

        self._ip = ip
        self._port = port

        try:
            if settings.mock_mode:
                from src.factorylm_plc.mock_plc import MockPLC
                self._client = MockPLC()
                self._client.connect()
                self._connected = True
                self._last_seen = datetime.now()
                logger.info("Connected to MockPLC (mock mode)")
                return {"success": True, "message": "Connected to MockPLC (mock mode)"}

            from src.factorylm_plc.modbus_client import ModbusTCPClient
            self._client = ModbusTCPClient(host=ip, port=port, timeout=3.0)
            if self._client.connect():
                self._connected = True
                self._last_seen = datetime.now()
                logger.info(f"Connected to PLC at {ip}:{port}")
                return {"success": True, "message": f"Connected to {ip}:{port}"}
            else:
                self._connected = False
                return {"success": False, "message": f"Failed to connect to {ip}:{port}"}
        except Exception as e:
            logger.error(f"Connection error: {e}")
            self._connected = False
            return {"success": False, "message": str(e)}

    def disconnect(self) -> None:
        """Disconnect from PLC."""
        if self._client:
            try:
                self._client.disconnect()
            except Exception:
                pass
        self._connected = False
        self._client = None
        logger.info("Disconnected from PLC")

    def get_status(self) -> Dict[str, Any]:
        """
        Get current connection status.

        Returns:
            Dict with connected, ip, port, last_seen
        """
        return {
            "connected": self.is_connected,
            "ip": self._ip,
            "port": self._port,
            "last_seen": self._last_seen.isoformat() if self._last_seen else None,
        }

    def read_io(self) -> Dict[str, Any]:
        """
        Read all I/O from PLC.

        Returns:
            Dict with coils, inputs, outputs, and registers
        """
        if not self.is_connected:
            raise ConnectionError("Not connected to PLC")

        # Read coils 0-17
        coils = self._client.read_coils(address=0, count=18)

        # Read registers 100-105
        registers = self._client.read_holding_registers(address=100, count=6)

        self._last_seen = datetime.now()

        # Build response with named values
        coil_data = {}
        input_data = {}
        output_data = {}

        for i, value in enumerate(coils):
            name = self.COIL_NAMES.get(i, f"coil_{i}")
            if i <= 6:
                coil_data[name] = value
            elif i <= 14:
                input_data[name] = value
            else:
                output_data[name] = value

        register_data = {}
        for i, value in enumerate(registers):
            addr = 100 + i
            name = self.REGISTER_NAMES.get(addr, f"register_{addr}")
            register_data[name] = value

        return {
            "coils": coil_data,
            "inputs": input_data,
            "outputs": output_data,
            "registers": register_data,
            "timestamp": datetime.now().isoformat(),
        }

    def write_coil(self, address: int, value: bool) -> Dict[str, Any]:
        """
        Write a coil value.

        Args:
            address: Coil address (must be in writable range)
            value: Boolean value to write

        Returns:
            Dict with success, address, value
        """
        if not self.is_connected:
            raise ConnectionError("Not connected to PLC")

        if address not in self.WRITABLE_COILS:
            raise ValueError(f"Address {address} is not writable. Writable: {self.WRITABLE_COILS}")

        success = self._client.write_coil(address=address, value=value)
        self._last_seen = datetime.now()

        return {
            "success": success,
            "address": address,
            "value": value,
            "name": self.COIL_NAMES.get(address, f"coil_{address}"),
        }


# Global singleton instance
plc_service = PLCConnectionService()
