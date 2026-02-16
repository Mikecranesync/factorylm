"""
Unit tests for ModbusTCPClient wrapper.

Tests use mocking to avoid requiring a real Modbus server.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from factorylm_plc.modbus.client import ModbusTCPClient


class TestModbusTCPClientConnection:
    """Test connection behavior."""

    @patch('factorylm_plc.modbus.client.ModbusTcpClient')
    def test_connect_success(self, mock_client_class):
        """Successful connection returns True."""
        mock_client = Mock()
        mock_client.connect.return_value = True
        mock_client.connected = True
        mock_client_class.return_value = mock_client

        client = ModbusTCPClient("192.168.1.100", 502)
        result = client.connect()

        assert result is True
        mock_client.connect.assert_called()

    @patch('factorylm_plc.modbus.client.ModbusTcpClient')
    def test_connect_failure_raises(self, mock_client_class):
        """Failed connection raises ConnectionError."""
        mock_client = Mock()
        mock_client.connect.return_value = False
        mock_client_class.return_value = mock_client

        client = ModbusTCPClient("192.168.1.100", 502, retries=2)

        with pytest.raises(ConnectionError):
            client.connect()

    @patch('factorylm_plc.modbus.client.ModbusTcpClient')
    def test_disconnect(self, mock_client_class):
        """Disconnect closes the connection."""
        mock_client = Mock()
        mock_client.connect.return_value = True
        mock_client.connected = True
        mock_client_class.return_value = mock_client

        client = ModbusTCPClient("192.168.1.100", 502)
        client.connect()
        client.disconnect()

        mock_client.close.assert_called_once()

    @patch('factorylm_plc.modbus.client.ModbusTcpClient')
    def test_is_connected(self, mock_client_class):
        """is_connected reflects actual connection state."""
        mock_client = Mock()
        mock_client.connect.return_value = True
        mock_client.connected = True
        mock_client_class.return_value = mock_client

        client = ModbusTCPClient("192.168.1.100", 502)

        # Not connected yet
        assert client.is_connected() is False

        # After connect
        client.connect()
        assert client.is_connected() is True


class TestModbusTCPClientReadRegisters:
    """Test register reading."""

    @patch('factorylm_plc.modbus.client.ModbusTcpClient')
    def test_read_registers_success(self, mock_client_class):
        """Successful read returns register values."""
        mock_result = Mock()
        mock_result.isError.return_value = False
        mock_result.registers = [100, 200, 300, 400]

        mock_client = Mock()
        mock_client.connect.return_value = True
        mock_client.connected = True
        mock_client.read_holding_registers.return_value = mock_result
        mock_client_class.return_value = mock_client

        client = ModbusTCPClient("192.168.1.100", 502)
        client.connect()
        values = client.read_registers(100, 4)

        assert values == [100, 200, 300, 400]
        mock_client.read_holding_registers.assert_called_with(
            address=100, count=4, slave=1
        )

    @patch('factorylm_plc.modbus.client.ModbusTcpClient')
    def test_read_registers_not_connected(self, mock_client_class):
        """Reading when not connected raises ConnectionError."""
        client = ModbusTCPClient("192.168.1.100", 502)

        with pytest.raises(ConnectionError):
            client.read_registers(100, 4)

    @patch('factorylm_plc.modbus.client.ModbusTcpClient')
    def test_read_registers_custom_unit(self, mock_client_class):
        """Can read from specific Modbus unit."""
        mock_result = Mock()
        mock_result.isError.return_value = False
        mock_result.registers = [500]

        mock_client = Mock()
        mock_client.connect.return_value = True
        mock_client.connected = True
        mock_client.read_holding_registers.return_value = mock_result
        mock_client_class.return_value = mock_client

        client = ModbusTCPClient("192.168.1.100", 502)
        client.connect()
        client.read_registers(100, 1, unit=5)

        mock_client.read_holding_registers.assert_called_with(
            address=100, count=1, slave=5
        )


class TestModbusTCPClientReadCoils:
    """Test coil reading."""

    @patch('factorylm_plc.modbus.client.ModbusTcpClient')
    def test_read_coils_success(self, mock_client_class):
        """Successful read returns coil values."""
        mock_result = Mock()
        mock_result.isError.return_value = False
        mock_result.bits = [True, False, True, False, False, False, False, False]

        mock_client = Mock()
        mock_client.connect.return_value = True
        mock_client.connected = True
        mock_client.read_coils.return_value = mock_result
        mock_client_class.return_value = mock_client

        client = ModbusTCPClient("192.168.1.100", 502)
        client.connect()
        values = client.read_coils(0, 3)

        assert values == [True, False, True]

    @patch('factorylm_plc.modbus.client.ModbusTcpClient')
    def test_read_coils_not_connected(self, mock_client_class):
        """Reading coils when not connected raises ConnectionError."""
        client = ModbusTCPClient("192.168.1.100", 502)

        with pytest.raises(ConnectionError):
            client.read_coils(0, 3)


class TestModbusTCPClientWriteRegister:
    """Test register writing."""

    @patch('factorylm_plc.modbus.client.ModbusTcpClient')
    def test_write_register_success(self, mock_client_class):
        """Successful write returns True."""
        mock_result = Mock()
        mock_result.isError.return_value = False

        mock_client = Mock()
        mock_client.connect.return_value = True
        mock_client.connected = True
        mock_client.write_register.return_value = mock_result
        mock_client_class.return_value = mock_client

        client = ModbusTCPClient("192.168.1.100", 502)
        client.connect()
        result = client.write_register(100, 1500)

        assert result is True
        mock_client.write_register.assert_called_with(
            address=100, value=1500, slave=1
        )

    @patch('factorylm_plc.modbus.client.ModbusTcpClient')
    def test_write_register_invalid_value(self, mock_client_class):
        """Writing invalid value raises ValueError."""
        mock_client = Mock()
        mock_client.connect.return_value = True
        mock_client.connected = True
        mock_client_class.return_value = mock_client

        client = ModbusTCPClient("192.168.1.100", 502)
        client.connect()

        with pytest.raises(ValueError):
            client.write_register(100, -1)

        with pytest.raises(ValueError):
            client.write_register(100, 70000)

    @patch('factorylm_plc.modbus.client.ModbusTcpClient')
    def test_write_register_not_connected(self, mock_client_class):
        """Writing when not connected raises ConnectionError."""
        client = ModbusTCPClient("192.168.1.100", 502)

        with pytest.raises(ConnectionError):
            client.write_register(100, 1000)


class TestModbusTCPClientWriteCoil:
    """Test coil writing."""

    @patch('factorylm_plc.modbus.client.ModbusTcpClient')
    def test_write_coil_success(self, mock_client_class):
        """Successful coil write returns True."""
        mock_result = Mock()
        mock_result.isError.return_value = False

        mock_client = Mock()
        mock_client.connect.return_value = True
        mock_client.connected = True
        mock_client.write_coil.return_value = mock_result
        mock_client_class.return_value = mock_client

        client = ModbusTCPClient("192.168.1.100", 502)
        client.connect()
        result = client.write_coil(0, True)

        assert result is True
        mock_client.write_coil.assert_called_with(address=0, value=True, slave=1)

    @patch('factorylm_plc.modbus.client.ModbusTcpClient')
    def test_write_coil_not_connected(self, mock_client_class):
        """Writing coil when not connected raises ConnectionError."""
        client = ModbusTCPClient("192.168.1.100", 502)

        with pytest.raises(ConnectionError):
            client.write_coil(0, True)


class TestModbusTCPClientContextManager:
    """Test context manager support."""

    @patch('factorylm_plc.modbus.client.ModbusTcpClient')
    def test_context_manager(self, mock_client_class):
        """Can use client as context manager."""
        mock_client = Mock()
        mock_client.connect.return_value = True
        mock_client.connected = True
        mock_client_class.return_value = mock_client

        with ModbusTCPClient("192.168.1.100", 502) as client:
            assert client.is_connected()

        mock_client.close.assert_called_once()


class TestModbusTCPClientRetry:
    """Test retry behavior."""

    @patch('factorylm_plc.modbus.client.ModbusTcpClient')
    @patch('time.sleep')
    def test_connect_retries(self, mock_sleep, mock_client_class):
        """Connection retries on failure."""
        mock_client = Mock()
        mock_client.connect.side_effect = [False, False, True]
        mock_client.connected = True
        mock_client_class.return_value = mock_client

        client = ModbusTCPClient("192.168.1.100", 502, retries=3)
        result = client.connect()

        assert result is True
        assert mock_client.connect.call_count == 3
