"""
Integration tests for PLC Client end-to-end workflows.

Uses MockPLC to test full operation flows without real hardware.
"""

import pytest
import time
from factorylm_plc import create_plc_client, MachineState, BasePLCClient


class TestFactoryFunction:
    """Test create_plc_client factory."""

    def test_create_mock_plc(self):
        """Factory creates MockPLC."""
        plc = create_plc_client("mock")
        assert plc is not None
        assert isinstance(plc, BasePLCClient)

    def test_create_micro820_plc(self):
        """Factory creates Micro820PLC."""
        plc = create_plc_client("micro820", host="192.168.1.100")
        assert plc is not None
        assert isinstance(plc, BasePLCClient)

    def test_unknown_plc_type_raises(self):
        """Factory raises ValueError for unknown type."""
        with pytest.raises(ValueError) as exc_info:
            create_plc_client("unknown_plc")

        assert "Unknown PLC type" in str(exc_info.value)


class TestMockPLCEndToEnd:
    """End-to-end tests using MockPLC."""

    def test_full_workflow(self):
        """Test complete read-modify-write cycle."""
        # Create client via factory
        plc = create_plc_client("mock")

        # Connect
        assert plc.connect() is True
        assert plc.is_connected() is True

        # Read initial state
        state = plc.read_state()
        assert state is not None
        assert isinstance(state, MachineState)
        assert state.motor_running is False
        assert state.motor_stopped is True

        # Start motor and set speed
        plc.start_motor()
        plc.set_motor_speed(1500)

        # Read updated state
        state = plc.read_state()
        assert state.motor_running is True
        assert state.motor_stopped is False
        assert state.motor_speed == 1500

        # Stop motor
        plc.stop_motor()
        state = plc.read_state()
        assert state.motor_running is False
        assert state.motor_stopped is True

        # Disconnect
        plc.disconnect()
        assert plc.is_connected() is False

    def test_context_manager_workflow(self):
        """Test using context manager."""
        with create_plc_client("mock") as plc:
            assert plc.is_connected() is True

            state = plc.read_state()
            assert state is not None
            assert state.is_healthy() is True

        # After exiting context, should be disconnected
        assert plc.is_connected() is False

    def test_fault_detection(self):
        """Test fault alarm detection."""
        with create_plc_client("mock") as plc:
            # Initially healthy
            state = plc.read_state()
            assert state.is_healthy() is True
            assert state.fault_alarm is False

            # Trigger fault
            plc.trigger_fault()
            state = plc.read_state()
            assert state.is_healthy() is False
            assert state.fault_alarm is True

            # Clear fault
            plc.clear_fault()
            state = plc.read_state()
            assert state.is_healthy() is True
            assert state.fault_alarm is False

    def test_motor_current_simulation(self):
        """Test that motor current varies with speed."""
        with create_plc_client("mock") as plc:
            # Start motor with low speed
            plc.start_motor()
            plc.set_motor_speed(500)
            state = plc.read_state()
            low_current = state.motor_current

            # Increase speed
            plc.set_motor_speed(2000)
            state = plc.read_state()
            high_current = state.motor_current

            # Higher speed = higher current
            assert high_current > low_current

    def test_state_serialization(self):
        """Test MachineState serialization roundtrip."""
        with create_plc_client("mock") as plc:
            plc.start_motor()
            plc.set_motor_speed(1000)
            state = plc.read_state()

            # Serialize to dict
            data = state.to_dict()
            assert isinstance(data, dict)
            assert "motor_speed" in data
            assert data["motor_speed"] == 1000

            # Deserialize back
            restored = MachineState.from_dict(data)
            assert restored.motor_speed == state.motor_speed
            assert restored.motor_running == state.motor_running
            assert restored.timestamp == state.timestamp


class TestMachineStateOperations:
    """Test MachineState helper operations."""

    def test_machine_state_str(self):
        """Test string representation."""
        with create_plc_client("mock") as plc:
            plc.start_motor()
            plc.set_motor_speed(1750)
            state = plc.read_state()

            s = str(state)
            assert "RUNNING" in s
            assert "1750" in s

    def test_machine_state_to_json_compatible(self):
        """Test that to_dict is JSON serializable."""
        import json

        with create_plc_client("mock") as plc:
            state = plc.read_state()
            data = state.to_dict()

            # Should be JSON serializable
            json_str = json.dumps(data)
            assert isinstance(json_str, str)

            # Should roundtrip through JSON
            parsed = json.loads(json_str)
            restored = MachineState.from_dict(parsed)
            assert restored.motor_speed == state.motor_speed


class TestMultiplePLCClients:
    """Test multiple concurrent PLC clients."""

    def test_multiple_mock_plcs(self):
        """Multiple MockPLC instances are independent."""
        plc1 = create_plc_client("mock")
        plc2 = create_plc_client("mock")

        plc1.connect()
        plc2.connect()

        # Set different speeds
        plc1.start_motor()
        plc1.set_motor_speed(1000)

        plc2.start_motor()
        plc2.set_motor_speed(2000)

        # States should be independent
        state1 = plc1.read_state()
        state2 = plc2.read_state()

        assert state1.motor_speed == 1000
        assert state2.motor_speed == 2000

        plc1.disconnect()
        plc2.disconnect()
