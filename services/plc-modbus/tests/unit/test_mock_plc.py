"""
Unit tests for MockPLC — the in-memory PLC simulator.

Tests connection lifecycle, register/coil read-write, helper methods
(start/stop motor, conveyor, e-stop, errors), simulation behaviour,
and state reading.

Migrated from:
  - plc-client/tests/unit/test_mock_plc.py (V1)
  - plc-client-factoryio/tests/test_mock_plc.py (V2)
Key V3 changes:
  - MockPLC returns FactoryState (not MachineState)
  - start_motor(speed) takes an optional speed parameter
  - Adds conveyor, sensor, e-stop, and error-code support
"""

import pytest
from datetime import datetime

from factorylm_plc.mock_plc import MockPLC
from factorylm_plc.models import FactoryState


# ---------------------------------------------------------------------------
# Connection lifecycle
# ---------------------------------------------------------------------------


class TestMockPLCConnection:
    """Test connect / disconnect / context-manager."""

    def test_initial_state_disconnected(self):
        """MockPLC starts disconnected."""
        plc = MockPLC()
        assert not plc.is_connected()

    def test_connect_succeeds(self):
        """connect() always returns True for mock."""
        plc = MockPLC()
        result = plc.connect()
        assert result is True
        assert plc.is_connected()

    def test_disconnect(self):
        """disconnect() sets connected to False."""
        plc = MockPLC()
        plc.connect()
        plc.disconnect()
        assert not plc.is_connected()

    def test_context_manager(self):
        """MockPLC works as a context manager."""
        with MockPLC() as plc:
            assert plc.is_connected()
        assert not plc.is_connected()

    def test_operations_require_connection(self):
        """Register/coil operations raise ConnectionError when not connected."""
        plc = MockPLC()

        with pytest.raises(ConnectionError):
            plc.read_holding_registers(100, 1)

        with pytest.raises(ConnectionError):
            plc.read_coils(0, 1)

        with pytest.raises(ConnectionError):
            plc.write_register(100, 50)

        with pytest.raises(ConnectionError):
            plc.write_coil(0, True)


# ---------------------------------------------------------------------------
# Register operations
# ---------------------------------------------------------------------------


class TestMockPLCRegisters:
    """Test holding-register read / write."""

    def test_read_holding_registers(self):
        """Can read a block of holding registers."""
        with MockPLC() as plc:
            values = plc.read_holding_registers(100, 6)
            assert len(values) == 6
            assert all(isinstance(v, int) for v in values)

    def test_write_and_read_register(self):
        """Write to a register, then read it back."""
        with MockPLC() as plc:
            plc.write_register(100, 75)
            values = plc.read_holding_registers(100, 1)
            assert values[0] == 75

    def test_initial_register_values(self):
        """Default registers: speed=0, temp≈250 (25.0 °C), pressure=100."""
        with MockPLC() as plc:
            values = plc.read_holding_registers(100, 6)
            assert values[0] == 0        # motor_speed
            assert 200 <= values[2] <= 300  # temperature raw ≈ 250


# ---------------------------------------------------------------------------
# Coil operations
# ---------------------------------------------------------------------------


class TestMockPLCCoils:
    """Test coil read / write."""

    def test_read_coils(self):
        """Can read a block of coils."""
        with MockPLC() as plc:
            values = plc.read_coils(0, 7)
            assert len(values) == 7
            assert all(isinstance(v, bool) for v in values)

    def test_write_and_read_coil(self):
        """Write to a coil, then read it back."""
        with MockPLC() as plc:
            plc.write_coil(0, True)
            values = plc.read_coils(0, 1)
            assert values[0] is True

    def test_motor_running_stopped_sync(self):
        """Setting motor_running syncs motor_stopped (and vice-versa)."""
        with MockPLC() as plc:
            # Initially stopped
            coils = plc.read_coils(0, 2)
            assert coils[0] is False  # motor_running
            assert coils[1] is True   # motor_stopped

            # Start motor
            plc.write_coil(0, True)
            coils = plc.read_coils(0, 2)
            assert coils[0] is True
            assert coils[1] is False


# ---------------------------------------------------------------------------
# State reading
# ---------------------------------------------------------------------------


class TestMockPLCState:
    """Test read_state returning FactoryState."""

    def test_read_state_returns_factory_state(self):
        """read_state() returns a FactoryState instance."""
        with MockPLC() as plc:
            state = plc.read_state()
            assert isinstance(state, FactoryState)
            assert hasattr(state, "motor_running")
            assert hasattr(state, "conveyor_running")
            assert hasattr(state, "e_stop_active")

    def test_read_state_reflects_changes(self):
        """State reflects register/coil changes made via helpers."""
        with MockPLC() as plc:
            plc.start_motor(80)
            state = plc.read_state()
            assert state.motor_running is True
            assert state.motor_speed == 80

            plc.stop_motor()
            state = plc.read_state()
            assert state.motor_running is False

    def test_initial_state_values(self):
        """Initial state: motor off, temp ≈ 25 °C, no fault."""
        with MockPLC() as plc:
            state = plc.read_state()
            assert state.motor_speed == 0
            assert state.motor_running is False
            assert state.fault_active is False
            assert 20.0 <= state.temperature <= 30.0

    def test_state_has_timestamp(self):
        """State includes a datetime timestamp."""
        with MockPLC() as plc:
            state = plc.read_state()
            assert isinstance(state.timestamp, datetime)

    def test_read_state_when_disconnected_raises(self):
        """read_state() raises ConnectionError when not connected."""
        plc = MockPLC()
        with pytest.raises(ConnectionError):
            plc.read_state()


# ---------------------------------------------------------------------------
# Helper methods
# ---------------------------------------------------------------------------


class TestMockPLCMotorHelpers:
    """Test start_motor / stop_motor."""

    def test_start_motor(self):
        """start_motor sets running=True and speed."""
        with MockPLC() as plc:
            plc.start_motor(75)
            state = plc.read_state()
            assert state.motor_running is True
            assert state.motor_speed == 75

    def test_start_motor_default_speed(self):
        """start_motor defaults to 50 % speed."""
        with MockPLC() as plc:
            plc.start_motor()
            state = plc.read_state()
            assert state.motor_speed == 50

    def test_stop_motor(self):
        """stop_motor sets running=False."""
        with MockPLC() as plc:
            plc.start_motor(50)
            plc.stop_motor()
            state = plc.read_state()
            assert state.motor_running is False


class TestMockPLCConveyorHelpers:
    """Test start_conveyor / stop_conveyor."""

    def test_start_conveyor(self):
        """start_conveyor sets conveyor_running=True and speed."""
        with MockPLC() as plc:
            plc.start_conveyor(60)
            state = plc.read_state()
            assert state.conveyor_running is True
            assert state.conveyor_speed == 60

    def test_stop_conveyor(self):
        """stop_conveyor sets conveyor_running=False and speed=0."""
        with MockPLC() as plc:
            plc.start_conveyor(50)
            plc.stop_conveyor()
            state = plc.read_state()
            assert state.conveyor_running is False
            assert state.conveyor_speed == 0


class TestMockPLCErrorHelpers:
    """Test trigger_error / clear_error."""

    def test_trigger_error(self):
        """trigger_error sets the error code and fault alarm."""
        with MockPLC() as plc:
            plc.trigger_error(2)
            state = plc.read_state()
            assert state.error_code == 2
            assert state.fault_active is True

    def test_clear_error(self):
        """clear_error resets error code and fault alarm."""
        with MockPLC() as plc:
            plc.trigger_error(1)
            plc.clear_error()
            state = plc.read_state()
            assert state.error_code == 0
            assert state.fault_active is False


class TestMockPLCEStopHelpers:
    """Test trigger_estop / release_estop."""

    def test_trigger_estop(self):
        """E-stop stops motor, conveyor, and sets e_stop_active."""
        with MockPLC() as plc:
            plc.start_motor(50)
            plc.start_conveyor(50)
            plc.trigger_estop()
            state = plc.read_state()
            assert state.e_stop_active is True
            assert state.motor_running is False
            assert state.conveyor_running is False

    def test_release_estop(self):
        """Releasing e-stop clears e_stop_active."""
        with MockPLC() as plc:
            plc.trigger_estop()
            plc.release_estop()
            state = plc.read_state()
            assert state.e_stop_active is False


# ---------------------------------------------------------------------------
# Simulation behaviour
# ---------------------------------------------------------------------------


class TestMockPLCSimulation:
    """Test realistic simulation (current varies with speed, etc.)."""

    def test_current_changes_with_speed(self):
        """Motor current increases with speed."""
        with MockPLC() as plc:
            plc.start_motor(0)
            state1 = plc.read_state()

            plc.start_motor(100)
            state2 = plc.read_state()

            assert state2.motor_current > state1.motor_current

    def test_custom_initial_state(self):
        """MockPLC accepts an initial_state dict override."""
        initial = {
            "motor_speed": 50,
            "temperature": 600,  # 60.0 °C raw
            "motor_running": True,
        }
        with MockPLC(initial_state=initial) as plc:
            state = plc.read_state()
            assert state.motor_speed == 50
            assert state.motor_running is True
            # Temperature may drift slightly due to simulation
            assert 55.0 <= state.temperature <= 65.0
