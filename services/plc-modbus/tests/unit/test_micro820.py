"""
Unit tests for Micro820PLC.

Tests the Micro 820-specific register/coil mapping, scale factors,
named read/write helpers, and read_state.  All Modbus I/O is mocked.

Migrated from plc-client/tests/unit/test_micro820.py (V1).
Key V3 changes:
  - Micro820PLC now extends ModbusTCPClient directly (not via a
    separate wrapper class)
  - Register/coil addresses stored in REGISTERS / COILS dicts
  - read_state returns a V3 MachineState (datetime timestamp,
    fault_active instead of fault_alarm)
  - Named helpers: read_register_by_name, read_all_registers, etc.
"""

import pytest
from unittest.mock import Mock, patch

from factorylm_plc.micro820 import Micro820PLC
from factorylm_plc.models import MachineState


class TestMicro820PLCRegisterMapping:
    """Test register and coil address dictionaries."""

    def test_register_addresses(self):
        """REGISTERS dict contains expected entries."""
        assert Micro820PLC.REGISTERS["motor_speed"] == 100
        assert Micro820PLC.REGISTERS["motor_current"] == 101
        assert Micro820PLC.REGISTERS["temperature"] == 102
        assert Micro820PLC.REGISTERS["pressure"] == 103

    def test_coil_addresses(self):
        """COILS dict contains expected entries."""
        assert Micro820PLC.COILS["motor_running"] == 0
        assert Micro820PLC.COILS["motor_stopped"] == 1
        assert Micro820PLC.COILS["fault_alarm"] == 2


class TestMicro820PLCInit:
    """Test constructor and defaults."""

    def test_inherits_modbus_defaults(self):
        """Constructor sets expected defaults inherited from ModbusTCPClient."""
        plc = Micro820PLC("192.168.1.100")
        assert plc.host == "192.168.1.100"
        assert plc.port == 502
        assert plc.timeout == 5.0
        assert plc.retries == 3
        assert plc.unit_id == 1


class TestMicro820PLCScaleFactors:
    """Test _apply_scale_factor."""

    def test_temperature_scale(self):
        """Temperature raw 450 → 45.0."""
        plc = Micro820PLC("192.168.1.100")
        assert plc._apply_scale_factor("temperature", 450) == 45.0

    def test_motor_current_scale(self):
        """Motor current raw 25 → 2.5."""
        plc = Micro820PLC("192.168.1.100")
        assert plc._apply_scale_factor("motor_current", 25) == 2.5

    def test_no_scale_factor(self):
        """Fields without a scale factor return float of raw value."""
        plc = Micro820PLC("192.168.1.100")
        assert plc._apply_scale_factor("motor_speed", 1500) == 1500.0


class TestMicro820PLCNamedAccess:
    """Test read/write by name helpers."""

    @patch("factorylm_plc.modbus_client.ModbusTcpClient")
    def test_read_register_by_name(self, mock_pymodbus_class):
        """read_register_by_name reads correct address and applies scale."""
        mock_result = Mock()
        mock_result.isError.return_value = False
        mock_result.registers = [450]

        mock_inner = Mock()
        mock_inner.connect.return_value = True
        mock_inner.connected = True
        mock_inner.read_holding_registers.return_value = mock_result
        mock_pymodbus_class.return_value = mock_inner

        plc = Micro820PLC("192.168.1.100")
        plc.connect()
        value = plc.read_register_by_name("temperature")

        assert value == 45.0  # 450 / 10

    @patch("factorylm_plc.modbus_client.ModbusTcpClient")
    def test_read_coil_by_name(self, mock_pymodbus_class):
        """read_coil_by_name reads correct address."""
        mock_result = Mock()
        mock_result.isError.return_value = False
        mock_result.bits = [True]

        mock_inner = Mock()
        mock_inner.connect.return_value = True
        mock_inner.connected = True
        mock_inner.read_coils.return_value = mock_result
        mock_pymodbus_class.return_value = mock_inner

        plc = Micro820PLC("192.168.1.100")
        plc.connect()
        value = plc.read_coil_by_name("motor_running")

        assert value is True

    def test_get_register_address_unknown_raises(self):
        """_get_register_address raises ValueError for unknown names."""
        plc = Micro820PLC("192.168.1.100")
        with pytest.raises(ValueError, match="Unknown register"):
            plc._get_register_address("nonexistent")

    def test_get_coil_address_unknown_raises(self):
        """_get_coil_address raises ValueError for unknown names."""
        plc = Micro820PLC("192.168.1.100")
        with pytest.raises(ValueError, match="Unknown coil"):
            plc._get_coil_address("nonexistent")


class TestMicro820PLCReadState:
    """Test read_state assembly."""

    @patch("factorylm_plc.modbus_client.ModbusTcpClient")
    def test_read_state_returns_machine_state(self, mock_pymodbus_class):
        """read_state returns a properly populated MachineState."""
        # Mock register read (addresses 100-103 → 4 values)
        mock_reg_result = Mock()
        mock_reg_result.isError.return_value = False
        mock_reg_result.registers = [1500, 25, 450, 100]

        # Mock coil read (addresses 0-2 → 3 values)
        mock_coil_result = Mock()
        mock_coil_result.isError.return_value = False
        mock_coil_result.bits = [True, False, False]

        mock_inner = Mock()
        mock_inner.connect.return_value = True
        mock_inner.connected = True
        mock_inner.read_holding_registers.return_value = mock_reg_result
        mock_inner.read_coils.return_value = mock_coil_result
        mock_pymodbus_class.return_value = mock_inner

        plc = Micro820PLC("192.168.1.100")
        plc.connect()
        state = plc.read_state()

        assert isinstance(state, MachineState)
        assert state.motor_speed == 1500
        assert state.motor_current == 2.5   # 25 / 10
        assert state.temperature == 45.0     # 450 / 10
        assert state.pressure == 100
        assert state.motor_running is True
        assert state.fault_active is False

    @patch("factorylm_plc.modbus_client.ModbusTcpClient")
    def test_read_state_not_connected_raises(self, mock_pymodbus_class):
        """read_state raises ConnectionError when not connected."""
        plc = Micro820PLC("192.168.1.100")
        with pytest.raises(ConnectionError):
            plc.read_state()
