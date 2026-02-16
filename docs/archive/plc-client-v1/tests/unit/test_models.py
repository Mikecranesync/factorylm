"""
Unit tests for MachineState model.

Tests serialization, deserialization, and helper methods.
"""

import pytest
import time
from factorylm_plc.models import MachineState


class TestMachineStateCreation:
    """Test MachineState instantiation."""

    def test_create_with_defaults(self):
        """Can create MachineState with minimal args."""
        state = MachineState(
            motor_speed=100,
            motor_current=5,
            temperature=25.0,
            pressure=100,
            motor_running=True,
            motor_stopped=False,
            fault_alarm=False,
        )
        assert state.motor_speed == 100
        assert state.motor_current == 5

    def test_timestamp_default(self):
        """Timestamp defaults to current time."""
        before = time.time()
        state = MachineState(
            motor_speed=0,
            motor_current=0,
            temperature=25.0,
            pressure=100,
            motor_running=False,
            motor_stopped=True,
            fault_alarm=False,
        )
        after = time.time()

        assert before <= state.timestamp <= after

    def test_raw_registers_default_empty(self):
        """raw_registers defaults to empty dict."""
        state = MachineState(
            motor_speed=0,
            motor_current=0,
            temperature=25.0,
            pressure=100,
            motor_running=False,
            motor_stopped=True,
            fault_alarm=False,
        )
        assert state.raw_registers == {}


class TestMachineStateSerialization:
    """Test to_dict and from_dict methods."""

    def test_to_dict(self):
        """to_dict returns all fields."""
        state = MachineState(
            motor_speed=1500,
            motor_current=10,
            temperature=45.5,
            pressure=120,
            motor_running=True,
            motor_stopped=False,
            fault_alarm=False,
            timestamp=1234567890.0,
            raw_registers={"test": 123},
        )

        d = state.to_dict()

        assert d["motor_speed"] == 1500
        assert d["motor_current"] == 10
        assert d["temperature"] == 45.5
        assert d["pressure"] == 120
        assert d["motor_running"] is True
        assert d["motor_stopped"] is False
        assert d["fault_alarm"] is False
        assert d["timestamp"] == 1234567890.0
        assert d["raw_registers"] == {"test": 123}

    def test_from_dict(self):
        """from_dict creates MachineState from dict."""
        d = {
            "motor_speed": 2000,
            "motor_current": 15,
            "temperature": 50.0,
            "pressure": 110,
            "motor_running": True,
            "motor_stopped": False,
            "fault_alarm": True,
            "timestamp": 9876543210.0,
            "raw_registers": {"coils": [True, False]},
        }

        state = MachineState.from_dict(d)

        assert state.motor_speed == 2000
        assert state.motor_current == 15
        assert state.temperature == 50.0
        assert state.pressure == 110
        assert state.motor_running is True
        assert state.motor_stopped is False
        assert state.fault_alarm is True
        assert state.timestamp == 9876543210.0
        assert state.raw_registers == {"coils": [True, False]}

    def test_roundtrip(self):
        """to_dict -> from_dict preserves data."""
        original = MachineState(
            motor_speed=1750,
            motor_current=12,
            temperature=38.5,
            pressure=105,
            motor_running=True,
            motor_stopped=False,
            fault_alarm=False,
            timestamp=time.time(),
            raw_registers={"registers": [100, 101, 102]},
        )

        d = original.to_dict()
        restored = MachineState.from_dict(d)

        assert restored.motor_speed == original.motor_speed
        assert restored.motor_current == original.motor_current
        assert restored.temperature == original.temperature
        assert restored.pressure == original.pressure
        assert restored.motor_running == original.motor_running
        assert restored.motor_stopped == original.motor_stopped
        assert restored.fault_alarm == original.fault_alarm
        assert restored.timestamp == original.timestamp
        assert restored.raw_registers == original.raw_registers


class TestMachineStateHealth:
    """Test is_healthy method."""

    def test_healthy_state(self):
        """Healthy when running, no fault, normal temp."""
        state = MachineState(
            motor_speed=1500,
            motor_current=10,
            temperature=40.0,
            pressure=100,
            motor_running=True,
            motor_stopped=False,
            fault_alarm=False,
        )
        assert state.is_healthy() is True

    def test_unhealthy_with_fault(self):
        """Unhealthy when fault alarm is active."""
        state = MachineState(
            motor_speed=1500,
            motor_current=10,
            temperature=40.0,
            pressure=100,
            motor_running=True,
            motor_stopped=False,
            fault_alarm=True,
        )
        assert state.is_healthy() is False

    def test_healthy_with_high_temperature(self):
        """is_healthy only checks fault_alarm (not temperature)."""
        state = MachineState(
            motor_speed=1500,
            motor_current=10,
            temperature=85.0,  # High temp, but no fault
            pressure=100,
            motor_running=True,
            motor_stopped=False,
            fault_alarm=False,
        )
        # Current implementation only checks fault_alarm
        assert state.is_healthy() is True

    def test_healthy_stopped_motor(self):
        """Healthy even when motor is stopped (if no fault)."""
        state = MachineState(
            motor_speed=0,
            motor_current=0,
            temperature=25.0,
            pressure=100,
            motor_running=False,
            motor_stopped=True,
            fault_alarm=False,
        )
        assert state.is_healthy() is True


class TestMachineStateString:
    """Test string representation."""

    def test_str_output(self):
        """__str__ returns human-readable format."""
        state = MachineState(
            motor_speed=1500,
            motor_current=10,
            temperature=40.0,
            pressure=100,
            motor_running=True,
            motor_stopped=False,
            fault_alarm=False,
        )

        s = str(state)

        assert "1500" in s  # motor_speed
        assert "40.0" in s or "40" in s  # temperature
        assert "running" in s.lower() or "motor" in s.lower()
