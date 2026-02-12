"""
Unit tests for FactoryIOMicro820 — the Factory I/O-specific PLC client.

Tests extended register/coil mapping, scene_name, read_state returning
FactoryState, helper methods, and error-code interpretation.  All Modbus
I/O is mocked.

NEW for V3 — no direct V1/V2 equivalent (V2 tested FactoryIO indirectly
via MockPLC and factory tests).
"""

import pytest
from unittest.mock import Mock, patch

from factorylm_plc.factory_io import FactoryIOMicro820
from factorylm_plc.models import FactoryState, ERROR_CODES


class TestFactoryIOMicro820RegisterMapping:
    """Test extended register and coil mappings."""

    def test_has_conveyor_register(self):
        """REGISTERS includes conveyor_speed."""
        assert "conveyor_speed" in FactoryIOMicro820.REGISTERS
        assert FactoryIOMicro820.REGISTERS["conveyor_speed"] == 104

    def test_has_error_code_register(self):
        """REGISTERS includes error_code."""
        assert "error_code" in FactoryIOMicro820.REGISTERS
        assert FactoryIOMicro820.REGISTERS["error_code"] == 105

    def test_has_conveyor_coil(self):
        """COILS includes conveyor_running."""
        assert "conveyor_running" in FactoryIOMicro820.COILS
        assert FactoryIOMicro820.COILS["conveyor_running"] == 3

    def test_has_sensor_coils(self):
        """COILS includes sensor_1 and sensor_2."""
        assert FactoryIOMicro820.COILS["sensor_1"] == 4
        assert FactoryIOMicro820.COILS["sensor_2"] == 5

    def test_has_estop_coil(self):
        """COILS includes e_stop."""
        assert FactoryIOMicro820.COILS["e_stop"] == 6


class TestFactoryIOMicro820Init:
    """Test constructor and scene_name."""

    def test_default_scene_name(self):
        """Default scene_name is 'sorting_station'."""
        client = FactoryIOMicro820("192.168.1.100")
        assert client.scene_name == "sorting_station"

    def test_custom_scene_name(self):
        """Custom scene_name is stored."""
        client = FactoryIOMicro820("192.168.1.100", scene_name="assembly_line")
        assert client.scene_name == "assembly_line"


class TestFactoryIOMicro820ErrorInterpretation:
    """Test interpret_error_code static method."""

    def test_known_codes(self):
        """Known error codes return the expected message."""
        assert FactoryIOMicro820.interpret_error_code(0) == "No error"
        assert FactoryIOMicro820.interpret_error_code(1) == "Motor overload"
        assert FactoryIOMicro820.interpret_error_code(2) == "Temperature high"
        assert FactoryIOMicro820.interpret_error_code(3) == "Conveyor jam"

    def test_unknown_code(self):
        """Unknown error code returns descriptive fallback."""
        result = FactoryIOMicro820.interpret_error_code(42)
        assert "Unknown error 42" in result


class TestFactoryIOMicro820ReadState:
    """Test read_state returns FactoryState."""

    @patch("factorylm_plc.modbus_client.ModbusTcpClient")
    def test_read_state_returns_factory_state(self, mock_pymodbus_class):
        """read_state returns a populated FactoryState."""
        # 6 registers: speed, current, temp, pressure, conveyor_speed, error_code
        mock_reg_result = Mock()
        mock_reg_result.isError.return_value = False
        mock_reg_result.registers = [80, 30, 550, 110, 60, 0]

        # 7 coils: motor_running, motor_stopped, fault, conveyor, s1, s2, estop
        mock_coil_result = Mock()
        mock_coil_result.isError.return_value = False
        mock_coil_result.bits = [True, False, False, True, True, False, False]

        mock_inner = Mock()
        mock_inner.connect.return_value = True
        mock_inner.connected = True
        mock_inner.read_holding_registers.return_value = mock_reg_result
        mock_inner.read_coils.return_value = mock_coil_result
        mock_pymodbus_class.return_value = mock_inner

        client = FactoryIOMicro820("192.168.1.100")
        client.connect()
        state = client.read_state()

        assert isinstance(state, FactoryState)
        assert state.motor_running is True
        assert state.motor_speed == 80
        assert state.motor_current == 3.0  # 30 / 10
        assert state.temperature == 55.0   # 550 / 10
        assert state.pressure == 110
        assert state.conveyor_speed == 60
        assert state.conveyor_running is True
        assert state.sensor_1_active is True
        assert state.sensor_2_active is False
        assert state.e_stop_active is False
        assert state.error_code == 0
