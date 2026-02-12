"""
Integration tests for PLC Client end-to-end workflows.

Uses MockPLC (via factory function) to test full operation flows
including read-modify-write cycles, fault detection, serialization,
and multi-client independence — all without real hardware.

Migrated from plc-client/tests/integration/test_end_to_end.py (V1).
Key V3 changes:
  - MachineState uses ``fault_active`` (not ``fault_alarm``)
  - MachineState.timestamp is a ``datetime`` (not float)
  - ``is_healthy()`` removed; fault checking uses ``fault_active``
  - FactoryState returned by MockPLC, extends MachineState
  - start_motor(speed) takes an optional speed argument
"""

import json
import pytest

from factorylm_plc import create_plc_client, MachineState, FactoryState, BasePLCClient


class TestFactoryFunction:
    """Test create_plc_client factory creates correct types."""

    def test_create_mock_plc(self):
        """Factory creates MockPLC (a BasePLCClient)."""
        plc = create_plc_client("mock")
        assert plc is not None
        assert isinstance(plc, BasePLCClient)

    def test_create_micro820_plc(self):
        """Factory creates Micro820PLC (a BasePLCClient)."""
        plc = create_plc_client("micro820", host="192.168.1.100")
        assert plc is not None
        assert isinstance(plc, BasePLCClient)

    def test_unknown_plc_type_raises(self):
        """Factory raises ValueError for unknown type."""
        with pytest.raises(ValueError, match="Unknown PLC type"):
            create_plc_client("unknown_plc")


class TestMockPLCEndToEnd:
    """End-to-end tests using MockPLC."""

    def test_full_workflow(self):
        """Complete connect → read → start → read → stop → disconnect."""
        plc = create_plc_client("mock")

        # Connect
        assert plc.connect() is True
        assert plc.is_connected() is True

        # Read initial state
        state = plc.read_state()
        assert state is not None
        assert isinstance(state, FactoryState)
        assert state.motor_running is False

        # Start motor and set speed
        plc.start_motor(75)

        # Read updated state
        state = plc.read_state()
        assert state.motor_running is True
        assert state.motor_speed == 75

        # Stop motor
        plc.stop_motor()
        state = plc.read_state()
        assert state.motor_running is False

        # Disconnect
        plc.disconnect()
        assert plc.is_connected() is False

    def test_context_manager_workflow(self):
        """Context manager auto-connects and auto-disconnects."""
        with create_plc_client("mock") as plc:
            assert plc.is_connected() is True
            state = plc.read_state()
            assert state is not None
            assert state.fault_active is False

        assert plc.is_connected() is False

    def test_fault_detection(self):
        """Trigger and clear fault alarm."""
        with create_plc_client("mock") as plc:
            # Initially no fault
            state = plc.read_state()
            assert state.fault_active is False

            # Trigger fault
            plc.trigger_error(1)
            state = plc.read_state()
            assert state.fault_active is True

            # Clear fault
            plc.clear_error()
            state = plc.read_state()
            assert state.fault_active is False

    def test_motor_current_simulation(self):
        """Motor current increases with speed."""
        with create_plc_client("mock") as plc:
            plc.start_motor(10)
            state = plc.read_state()
            low_current = state.motor_current

            plc.start_motor(100)
            state = plc.read_state()
            high_current = state.motor_current

            assert high_current > low_current


class TestStateSerialization:
    """Test MachineState / FactoryState serialization round-trips."""

    def test_to_dict_roundtrip_json(self):
        """to_dict → JSON → parse produces consistent data."""
        with create_plc_client("mock") as plc:
            plc.start_motor(60)
            state = plc.read_state()

            data = state.to_dict()
            assert isinstance(data, dict)
            assert data["motor_speed"] == 60

            # JSON roundtrip
            json_str = json.dumps(data)
            assert isinstance(json_str, str)

            parsed = json.loads(json_str)
            assert parsed["motor_speed"] == 60


class TestMultiplePLCClients:
    """Test multiple concurrent mock PLC clients are independent."""

    def test_independent_state(self):
        """Two MockPLC instances maintain independent state."""
        plc1 = create_plc_client("mock")
        plc2 = create_plc_client("mock")

        plc1.connect()
        plc2.connect()

        plc1.start_motor(30)
        plc2.start_motor(90)

        state1 = plc1.read_state()
        state2 = plc2.read_state()

        assert state1.motor_speed == 30
        assert state2.motor_speed == 90

        plc1.disconnect()
        plc2.disconnect()


class TestConveyorEndToEnd:
    """Test conveyor operations end-to-end."""

    def test_conveyor_start_stop(self):
        """Start and stop conveyor, verify state changes."""
        with create_plc_client("mock") as plc:
            plc.start_conveyor(70)
            state = plc.read_state()
            assert state.conveyor_running is True
            assert state.conveyor_speed == 70

            plc.stop_conveyor()
            state = plc.read_state()
            assert state.conveyor_running is False
            assert state.conveyor_speed == 0


class TestEStopEndToEnd:
    """Test emergency stop end-to-end."""

    def test_estop_stops_everything(self):
        """E-stop halts motor and conveyor."""
        with create_plc_client("mock") as plc:
            plc.start_motor(50)
            plc.start_conveyor(50)

            plc.trigger_estop()
            state = plc.read_state()

            assert state.e_stop_active is True
            assert state.motor_running is False
            assert state.conveyor_running is False

            plc.release_estop()
            state = plc.read_state()
            assert state.e_stop_active is False
