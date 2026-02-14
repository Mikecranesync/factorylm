"""
Unit tests for ModbusTCPClient wrapper.

Tests connection lifecycle, register/coil read/write operations, and
error handling using mocks (no real Modbus server required).

Migrated from plc-client/tests/unit/test_modbus_client.py (V1).
Key V3 changes:
  - pymodbus calls now use ``device_id=`` instead of deprecated ``slave=``
  - ModbusTCPClient is imported from ``factorylm_plc.modbus_client``
    (V1 used ``factorylm_plc.modbus.client``)
  - V3 connect() returns False on failure instead of raising ConnectionError
  - V3 uses ``_ensure_connected`` guard; no ``retries`` connect-loop in connect()
"""

import pytest
from unittest.mock import Mock, patch, PropertyMock

from factorylm_plc.modbus_client import ModbusTCPClient


class TestModbusTCPClientConnection:
    """Test connection lifecycle."""

    @patch("factorylm_plc.modbus_client.ModbusTcpClient")
    def test_connect_success(self, mock_pymodbus_class):
        """Successful connection sets internal state and returns True."""
        mock_inner = Mock()
        mock_inner.connect.return_value = True
        mock_inner.connected = True
        mock_pymodbus_class.return_value = mock_inner

        client = ModbusTCPClient("192.168.1.100", 502)
        result = client.connect()

        assert result is True
        assert client.is_connected() is True

    @patch("factorylm_plc.modbus_client.ModbusTcpClient")
    def test_connect_failure_returns_false(self, mock_pymodbus_class):
        """Failed connection returns False (V3 does not raise)."""
        mock_inner = Mock()
        mock_inner.connect.return_value = False
        mock_inner.connected = False
        mock_pymodbus_class.return_value = mock_inner

        client = ModbusTCPClient("192.168.1.100", 502)
        result = client.connect()

        assert result is False

    @patch("factorylm_plc.modbus_client.ModbusTcpClient")
    def test_disconnect(self, mock_pymodbus_class):
        """Disconnect closes the underlying pymodbus client."""
        mock_inner = Mock()
        mock_inner.connect.return_value = True
        mock_inner.connected = True
        mock_pymodbus_class.return_value = mock_inner

        client = ModbusTCPClient("192.168.1.100", 502)
        client.connect()
        client.disconnect()

        mock_inner.close.assert_called_once()
        assert client.is_connected() is False

    @patch("factorylm_plc.modbus_client.ModbusTcpClient")
    def test_is_connected_before_connect(self, mock_pymodbus_class):
        """is_connected returns False before connect() is called."""
        client = ModbusTCPClient("192.168.1.100", 502)
        assert client.is_connected() is False

    @patch("factorylm_plc.modbus_client.ModbusTcpClient")
    def test_context_manager(self, mock_pymodbus_class):
        """Client works as a context manager (connect on enter, close on exit)."""
        mock_inner = Mock()
        mock_inner.connect.return_value = True
        mock_inner.connected = True
        mock_pymodbus_class.return_value = mock_inner

        with ModbusTCPClient("192.168.1.100", 502) as client:
            assert client.is_connected() is True

        mock_inner.close.assert_called_once()


class TestModbusTCPClientReadRegisters:
    """Test holding register reads."""

    @patch("factorylm_plc.modbus_client.ModbusTcpClient")
    def test_read_holding_registers_success(self, mock_pymodbus_class):
        """Successful read returns register values list."""
        mock_result = Mock()
        mock_result.isError.return_value = False
        mock_result.registers = [100, 200, 300, 400]

        mock_inner = Mock()
        mock_inner.connect.return_value = True
        mock_inner.connected = True
        mock_inner.read_holding_registers.return_value = mock_result
        mock_pymodbus_class.return_value = mock_inner

        client = ModbusTCPClient("192.168.1.100", 502)
        client.connect()
        values = client.read_holding_registers(100, 4)

        assert values == [100, 200, 300, 400]
        # V3 uses device_id= (not slave=)
        mock_inner.read_holding_registers.assert_called_with(
            address=100, count=4, device_id=1
        )

    @patch("factorylm_plc.modbus_client.ModbusTcpClient")
    def test_read_holding_registers_custom_unit_id(self, mock_pymodbus_class):
        """unit_id is forwarded as device_id to pymodbus."""
        mock_result = Mock()
        mock_result.isError.return_value = False
        mock_result.registers = [500]

        mock_inner = Mock()
        mock_inner.connect.return_value = True
        mock_inner.connected = True
        mock_inner.read_holding_registers.return_value = mock_result
        mock_pymodbus_class.return_value = mock_inner

        client = ModbusTCPClient("192.168.1.100", 502, unit_id=5)
        client.connect()
        client.read_holding_registers(100, 1)

        mock_inner.read_holding_registers.assert_called_with(
            address=100, count=1, device_id=5
        )

    @patch("factorylm_plc.modbus_client.ModbusTcpClient")
    def test_read_holding_registers_not_connected_raises(self, mock_pymodbus_class):
        """Reading when not connected raises ConnectionError."""
        client = ModbusTCPClient("192.168.1.100", 502)

        with pytest.raises(ConnectionError):
            client.read_holding_registers(100, 4)

    @patch("factorylm_plc.modbus_client.ModbusTcpClient")
    def test_read_holding_registers_error_response_raises(self, mock_pymodbus_class):
        """Modbus error response raises IOError."""
        mock_result = Mock()
        mock_result.isError.return_value = True

        mock_inner = Mock()
        mock_inner.connect.return_value = True
        mock_inner.connected = True
        mock_inner.read_holding_registers.return_value = mock_result
        mock_pymodbus_class.return_value = mock_inner

        client = ModbusTCPClient("192.168.1.100", 502)
        client.connect()

        with pytest.raises(IOError):
            client.read_holding_registers(100, 4)


class TestModbusTCPClientReadCoils:
    """Test coil reads."""

    @patch("factorylm_plc.modbus_client.ModbusTcpClient")
    def test_read_coils_success(self, mock_pymodbus_class):
        """Successful read returns only requested number of coil values."""
        mock_result = Mock()
        mock_result.isError.return_value = False
        mock_result.bits = [True, False, True, False, False, False, False, False]

        mock_inner = Mock()
        mock_inner.connect.return_value = True
        mock_inner.connected = True
        mock_inner.read_coils.return_value = mock_result
        mock_pymodbus_class.return_value = mock_inner

        client = ModbusTCPClient("192.168.1.100", 502)
        client.connect()
        values = client.read_coils(0, 3)

        assert values == [True, False, True]
        mock_inner.read_coils.assert_called_with(
            address=0, count=3, device_id=1
        )

    @patch("factorylm_plc.modbus_client.ModbusTcpClient")
    def test_read_coils_not_connected_raises(self, mock_pymodbus_class):
        """Reading coils when not connected raises ConnectionError."""
        client = ModbusTCPClient("192.168.1.100", 502)

        with pytest.raises(ConnectionError):
            client.read_coils(0, 3)


class TestModbusTCPClientWriteRegister:
    """Test register writes."""

    @patch("factorylm_plc.modbus_client.ModbusTcpClient")
    def test_write_register_success(self, mock_pymodbus_class):
        """Successful write returns True and uses device_id."""
        mock_result = Mock()
        mock_result.isError.return_value = False

        mock_inner = Mock()
        mock_inner.connect.return_value = True
        mock_inner.connected = True
        mock_inner.write_register.return_value = mock_result
        mock_pymodbus_class.return_value = mock_inner

        client = ModbusTCPClient("192.168.1.100", 502)
        client.connect()
        result = client.write_register(100, 1500)

        assert result is True
        mock_inner.write_register.assert_called_with(
            address=100, value=1500, device_id=1
        )

    @patch("factorylm_plc.modbus_client.ModbusTcpClient")
    def test_write_register_not_connected_raises(self, mock_pymodbus_class):
        """Writing when not connected raises ConnectionError."""
        client = ModbusTCPClient("192.168.1.100", 502)

        with pytest.raises(ConnectionError):
            client.write_register(100, 1000)

    @patch("factorylm_plc.modbus_client.ModbusTcpClient")
    def test_write_register_error_response(self, mock_pymodbus_class):
        """Error response from write returns False."""
        mock_result = Mock()
        mock_result.isError.return_value = True

        mock_inner = Mock()
        mock_inner.connect.return_value = True
        mock_inner.connected = True
        mock_inner.write_register.return_value = mock_result
        mock_pymodbus_class.return_value = mock_inner

        client = ModbusTCPClient("192.168.1.100", 502)
        client.connect()
        result = client.write_register(100, 1500)

        assert result is False


class TestModbusTCPClientWriteCoil:
    """Test coil writes."""

    @patch("factorylm_plc.modbus_client.ModbusTcpClient")
    def test_write_coil_success(self, mock_pymodbus_class):
        """Successful coil write returns True and uses device_id."""
        mock_result = Mock()
        mock_result.isError.return_value = False

        mock_inner = Mock()
        mock_inner.connect.return_value = True
        mock_inner.connected = True
        mock_inner.write_coil.return_value = mock_result
        mock_pymodbus_class.return_value = mock_inner

        client = ModbusTCPClient("192.168.1.100", 502)
        client.connect()
        result = client.write_coil(0, True)

        assert result is True
        mock_inner.write_coil.assert_called_with(
            address=0, value=True, device_id=1
        )

    @patch("factorylm_plc.modbus_client.ModbusTcpClient")
    def test_write_coil_not_connected_raises(self, mock_pymodbus_class):
        """Writing coil when not connected raises ConnectionError."""
        client = ModbusTCPClient("192.168.1.100", 502)

        with pytest.raises(ConnectionError):
            client.write_coil(0, True)


class TestModbusTCPClientReadState:
    """Test read_state behavior."""

    @patch("factorylm_plc.modbus_client.ModbusTcpClient")
    def test_read_state_raises_not_implemented(self, mock_pymodbus_class):
        """ModbusTCPClient.read_state raises NotImplementedError."""
        mock_inner = Mock()
        mock_inner.connect.return_value = True
        mock_inner.connected = True
        mock_pymodbus_class.return_value = mock_inner

        client = ModbusTCPClient("192.168.1.100", 502)
        client.connect()

        with pytest.raises(NotImplementedError):
            client.read_state()


class TestModbusTCPClientInit:
    """Test constructor defaults."""

    def test_default_values(self):
        """Constructor sets expected defaults."""
        client = ModbusTCPClient("10.0.0.1")
        assert client.host == "10.0.0.1"
        assert client.port == 502
        assert client.timeout == 5.0
        assert client.retries == 3
        assert client.unit_id == 1

    def test_custom_values(self):
        """Constructor accepts custom parameters."""
        client = ModbusTCPClient("10.0.0.2", port=5020, timeout=10.0, retries=5, unit_id=3)
        assert client.port == 5020
        assert client.timeout == 10.0
        assert client.retries == 5
        assert client.unit_id == 3
