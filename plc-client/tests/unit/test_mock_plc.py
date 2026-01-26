"""
Unit tests for MockPLC.

Tests the in-memory PLC simulator behavior.
"""

import pytest
import time
from factorylm_plc.plc.mock_plc import MockPLC
from factorylm_plc.models import MachineState


class TestMockPLCConnection:
    """Test connection behavior."""

    def test_initial_state_disconnected(self):
        """MockPLC starts disconnected."""
        plc = MockPLC()
        assert not plc.is_connected()

    def test_connect_succeeds(self):
        """Connect always succeeds for MockPLC."""
        plc = MockPLC()
        result = plc.connect()
        assert result is True
        assert plc.is_connected()

    def test_disconnect(self):
        """Disconnect sets connected to False."""
        plc = MockPLC()
        plc.connect()
        plc.disconnect()
        assert not plc.is_connected()

    def test_context_manager(self):
        """Test with statement support."""
        with MockPLC() as plc:
            assert plc.is_connected()
        assert not plc.is_connected()


class TestMockPLCReadState:
    """Test read_state behavior."""

    def test_read_state_when_connected(self):
        """Can read state when connected."""
        plc = MockPLC()
        plc.connect()
        state = plc.read_state()
        assert state is not None
        assert isinstance(state, MachineState)

    def test_read_state_when_disconnected(self):
        """Returns None when disconnected."""
        plc = MockPLC()
        state = plc.read_state()
        assert state is None

    def test_initial_state_values(self):
        """Check initial register/coil values."""
        plc = MockPLC()
        plc.connect()
        state = plc.read_state()

        assert state.motor_speed == 0
        assert state.motor_current == 0
        assert state.temperature == 25.0  # 250 / 10
        assert state.pressure == 100
        assert state.motor_running is False
        assert state.motor_stopped is True
        assert state.fault_alarm is False

    def test_state_has_timestamp(self):
        """State includes timestamp."""
        plc = MockPLC()
        plc.connect()
        before = time.time()
        state = plc.read_state()
        after = time.time()

        assert before <= state.timestamp <= after


class TestMockPLCRegisterWrite:
    """Test register writing."""

    def test_write_register(self):
        """Can write to registers."""
        plc = MockPLC()
        plc.connect()

        result = plc.write_register(100, 1500)
        assert result is True

        state = plc.read_state()
        assert state.motor_speed == 1500

    def test_write_register_disconnected_raises(self):
        """Writing when disconnected raises ConnectionError."""
        plc = MockPLC()
        with pytest.raises(ConnectionError):
            plc.write_register(100, 1000)

    def test_write_register_invalid_value_raises(self):
        """Invalid register value raises ValueError."""
        plc = MockPLC()
        plc.connect()

        with pytest.raises(ValueError):
            plc.write_register(100, -1)

        with pytest.raises(ValueError):
            plc.write_register(100, 70000)

    def test_set_motor_speed(self):
        """Convenience method for motor speed."""
        plc = MockPLC()
        plc.connect()

        plc.set_motor_speed(2000)
        state = plc.read_state()
        assert state.motor_speed == 2000


class TestMockPLCCoilWrite:
    """Test coil writing."""

    def test_write_coil(self):
        """Can write to coils."""
        plc = MockPLC()
        plc.connect()

        result = plc.write_coil(0, True)
        assert result is True

        state = plc.read_state()
        assert state.motor_running is True

    def test_write_coil_disconnected_raises(self):
        """Writing when disconnected raises ConnectionError."""
        plc = MockPLC()
        with pytest.raises(ConnectionError):
            plc.write_coil(0, True)

    def test_start_motor(self):
        """Start motor sets running=True, stopped=False."""
        plc = MockPLC()
        plc.connect()

        plc.start_motor()
        state = plc.read_state()

        assert state.motor_running is True
        assert state.motor_stopped is False

    def test_stop_motor(self):
        """Stop motor sets stopped=True, running=False."""
        plc = MockPLC()
        plc.connect()
        plc.start_motor()

        plc.stop_motor()
        state = plc.read_state()

        assert state.motor_stopped is True
        assert state.motor_running is False

    def test_trigger_fault(self):
        """Can trigger fault alarm."""
        plc = MockPLC()
        plc.connect()

        plc.trigger_fault()
        state = plc.read_state()
        assert state.fault_alarm is True

    def test_clear_fault(self):
        """Can clear fault alarm."""
        plc = MockPLC()
        plc.connect()
        plc.trigger_fault()

        plc.clear_fault()
        state = plc.read_state()
        assert state.fault_alarm is False


class TestMockPLCSimulation:
    """Test realistic simulation behavior."""

    def test_current_varies_with_speed(self):
        """Motor current increases with speed."""
        plc = MockPLC()
        plc.connect()
        plc.start_motor()

        plc.set_motor_speed(0)
        state = plc.read_state()
        current_at_0 = state.motor_current

        plc.set_motor_speed(1000)
        state = plc.read_state()
        current_at_1000 = state.motor_current

        assert current_at_1000 > current_at_0

    def test_no_current_when_stopped(self):
        """No motor current when motor is stopped."""
        plc = MockPLC()
        plc.connect()

        # Ensure motor is stopped
        plc.stop_motor()
        state = plc.read_state()

        assert state.motor_current == 0

    def test_reset_returns_to_initial_state(self):
        """Reset restores initial values."""
        plc = MockPLC()
        plc.connect()

        # Change some values
        plc.start_motor()
        plc.set_motor_speed(1500)
        plc.trigger_fault()

        # Reset
        plc.reset()
        state = plc.read_state()

        assert state.motor_speed == 0
        assert state.motor_running is False
        assert state.motor_stopped is True
        assert state.fault_alarm is False


class TestMockPLCRawRegisters:
    """Test raw register access."""

    def test_raw_registers_in_state(self):
        """State includes raw register data."""
        plc = MockPLC()
        plc.connect()
        state = plc.read_state()

        assert "registers" in state.raw_registers
        assert "coils" in state.raw_registers
        assert isinstance(state.raw_registers["registers"], dict)
        assert isinstance(state.raw_registers["coils"], dict)
