"""
Unit tests for Micro820PLC.

Tests use mocking to avoid requiring a real PLC.
"""

import pytest
from unittest.mock import Mock, patch
from factorylm_plc.plc.micro820 import Micro820PLC
from factorylm_plc.models import MachineState


class TestMicro820PLCConnection:
    """Test connection behavior."""

    @patch('factorylm_plc.plc.micro820.ModbusTCPClient')
    def test_connect_success(self, mock_modbus_class):
        """Successful connection returns True."""
        mock_modbus = Mock()
        mock_modbus_class.return_value = mock_modbus

        plc = Micro820PLC("192.168.1.100")
        result = plc.connect()

        assert result is True
        mock_modbus.connect.assert_called_once()

    @patch('factorylm_plc.plc.micro820.ModbusTCPClient')
    def test_connect_failure(self, mock_modbus_class):
        """Failed connection raises ConnectionError."""
        mock_modbus = Mock()
        mock_modbus.connect.side_effect = ConnectionError("Connection refused")
        mock_modbus_class.return_value = mock_modbus

        plc = Micro820PLC("192.168.1.100")

        with pytest.raises(ConnectionError):
            plc.connect()

    @patch('factorylm_plc.plc.micro820.ModbusTCPClient')
    def test_disconnect(self, mock_modbus_class):
        """Disconnect calls underlying Modbus disconnect."""
        mock_modbus = Mock()
        mock_modbus_class.return_value = mock_modbus

        plc = Micro820PLC("192.168.1.100")
        plc.connect()
        plc.disconnect()

        mock_modbus.disconnect.assert_called_once()

    @patch('factorylm_plc.plc.micro820.ModbusTCPClient')
    def test_is_connected(self, mock_modbus_class):
        """is_connected reflects both internal and Modbus state."""
        mock_modbus = Mock()
        mock_modbus.is_connected.return_value = True
        mock_modbus_class.return_value = mock_modbus

        plc = Micro820PLC("192.168.1.100")

        # Not connected initially
        assert plc.is_connected() is False

        # After connect
        plc.connect()
        assert plc.is_connected() is True


class TestMicro820PLCReadState:
    """Test state reading."""

    @patch('factorylm_plc.plc.micro820.ModbusTCPClient')
    def test_read_state_success(self, mock_modbus_class):
        """Successful read returns MachineState."""
        mock_modbus = Mock()
        mock_modbus.is_connected.return_value = True
        mock_modbus.read_registers.return_value = [1500, 10, 450, 100]  # speed, current, temp*10, pressure
        mock_modbus.read_coils.return_value = [True, False, False]  # running, stopped, fault
        mock_modbus_class.return_value = mock_modbus

        plc = Micro820PLC("192.168.1.100")
        plc.connect()
        state = plc.read_state()

        assert state is not None
        assert isinstance(state, MachineState)
        assert state.motor_speed == 1500
        assert state.motor_current == 10
        assert state.temperature == 45.0  # 450 / 10
        assert state.pressure == 100
        assert state.motor_running is True
        assert state.motor_stopped is False
        assert state.fault_alarm is False

    @patch('factorylm_plc.plc.micro820.ModbusTCPClient')
    def test_read_state_temperature_scaling(self, mock_modbus_class):
        """Temperature is correctly divided by 10."""
        mock_modbus = Mock()
        mock_modbus.is_connected.return_value = True
        mock_modbus.read_registers.return_value = [0, 0, 255, 0]  # 25.5°C
        mock_modbus.read_coils.return_value = [False, True, False]
        mock_modbus_class.return_value = mock_modbus

        plc = Micro820PLC("192.168.1.100")
        plc.connect()
        state = plc.read_state()

        assert state.temperature == 25.5

    @patch('factorylm_plc.plc.micro820.ModbusTCPClient')
    def test_read_state_when_not_connected(self, mock_modbus_class):
        """Returns None when not connected."""
        plc = Micro820PLC("192.168.1.100")
        state = plc.read_state()

        assert state is None

    @patch('factorylm_plc.plc.micro820.ModbusTCPClient')
    def test_read_state_includes_raw_registers(self, mock_modbus_class):
        """State includes raw register data for debugging."""
        mock_modbus = Mock()
        mock_modbus.is_connected.return_value = True
        mock_modbus.read_registers.return_value = [100, 5, 250, 100]
        mock_modbus.read_coils.return_value = [False, True, False]
        mock_modbus_class.return_value = mock_modbus

        plc = Micro820PLC("192.168.1.100")
        plc.connect()
        state = plc.read_state()

        assert "registers" in state.raw_registers
        assert "coils" in state.raw_registers

    @patch('factorylm_plc.plc.micro820.ModbusTCPClient')
    def test_read_state_has_timestamp(self, mock_modbus_class):
        """State includes timestamp."""
        mock_modbus = Mock()
        mock_modbus.is_connected.return_value = True
        mock_modbus.read_registers.return_value = [0, 0, 250, 100]
        mock_modbus.read_coils.return_value = [False, True, False]
        mock_modbus_class.return_value = mock_modbus

        plc = Micro820PLC("192.168.1.100")
        plc.connect()
        state = plc.read_state()

        assert state.timestamp > 0


class TestMicro820PLCWriteOperations:
    """Test write operations."""

    @patch('factorylm_plc.plc.micro820.ModbusTCPClient')
    def test_write_register(self, mock_modbus_class):
        """Can write to registers."""
        mock_modbus = Mock()
        mock_modbus.is_connected.return_value = True
        mock_modbus.write_register.return_value = True
        mock_modbus_class.return_value = mock_modbus

        plc = Micro820PLC("192.168.1.100")
        plc.connect()
        result = plc.write_register(100, 2000)

        assert result is True
        mock_modbus.write_register.assert_called_with(100, 2000)

    @patch('factorylm_plc.plc.micro820.ModbusTCPClient')
    def test_write_register_not_connected(self, mock_modbus_class):
        """Writing when not connected raises ConnectionError."""
        plc = Micro820PLC("192.168.1.100")

        with pytest.raises(ConnectionError):
            plc.write_register(100, 1000)

    @patch('factorylm_plc.plc.micro820.ModbusTCPClient')
    def test_write_coil(self, mock_modbus_class):
        """Can write to coils."""
        mock_modbus = Mock()
        mock_modbus.is_connected.return_value = True
        mock_modbus.write_coil.return_value = True
        mock_modbus_class.return_value = mock_modbus

        plc = Micro820PLC("192.168.1.100")
        plc.connect()
        result = plc.write_coil(0, True)

        assert result is True
        mock_modbus.write_coil.assert_called_with(0, True)

    @patch('factorylm_plc.plc.micro820.ModbusTCPClient')
    def test_write_coil_not_connected(self, mock_modbus_class):
        """Writing coil when not connected raises ConnectionError."""
        plc = Micro820PLC("192.168.1.100")

        with pytest.raises(ConnectionError):
            plc.write_coil(0, True)


class TestMicro820PLCConvenienceMethods:
    """Test convenience methods."""

    @patch('factorylm_plc.plc.micro820.ModbusTCPClient')
    def test_set_motor_speed(self, mock_modbus_class):
        """set_motor_speed writes to correct register."""
        mock_modbus = Mock()
        mock_modbus.is_connected.return_value = True
        mock_modbus.write_register.return_value = True
        mock_modbus_class.return_value = mock_modbus

        plc = Micro820PLC("192.168.1.100")
        plc.connect()
        plc.set_motor_speed(1750)

        mock_modbus.write_register.assert_called_with(100, 1750)

    @patch('factorylm_plc.plc.micro820.ModbusTCPClient')
    def test_start_motor(self, mock_modbus_class):
        """start_motor writes True to running coil."""
        mock_modbus = Mock()
        mock_modbus.is_connected.return_value = True
        mock_modbus.write_coil.return_value = True
        mock_modbus_class.return_value = mock_modbus

        plc = Micro820PLC("192.168.1.100")
        plc.connect()
        plc.start_motor()

        mock_modbus.write_coil.assert_called_with(0, True)

    @patch('factorylm_plc.plc.micro820.ModbusTCPClient')
    def test_stop_motor(self, mock_modbus_class):
        """stop_motor writes True to stopped coil."""
        mock_modbus = Mock()
        mock_modbus.is_connected.return_value = True
        mock_modbus.write_coil.return_value = True
        mock_modbus_class.return_value = mock_modbus

        plc = Micro820PLC("192.168.1.100")
        plc.connect()
        plc.stop_motor()

        mock_modbus.write_coil.assert_called_with(1, True)


class TestMicro820PLCRegisterMapping:
    """Test register/coil address mappings."""

    def test_register_addresses(self):
        """Verify register address constants."""
        assert Micro820PLC.REG_MOTOR_SPEED == 100
        assert Micro820PLC.REG_MOTOR_CURRENT == 101
        assert Micro820PLC.REG_TEMPERATURE == 102
        assert Micro820PLC.REG_PRESSURE == 103

    def test_coil_addresses(self):
        """Verify coil address constants."""
        assert Micro820PLC.COIL_MOTOR_RUNNING == 0
        assert Micro820PLC.COIL_MOTOR_STOPPED == 1
        assert Micro820PLC.COIL_FAULT_ALARM == 2


class TestMicro820PLCRepr:
    """Test string representation."""

    @patch('factorylm_plc.plc.micro820.ModbusTCPClient')
    def test_repr(self, mock_modbus_class):
        """repr includes host and connection status."""
        mock_modbus = Mock()
        mock_modbus.is_connected.return_value = False
        mock_modbus_class.return_value = mock_modbus

        plc = Micro820PLC("192.168.1.100")

        r = repr(plc)

        assert "192.168.1.100" in r
        assert "Micro820PLC" in r
