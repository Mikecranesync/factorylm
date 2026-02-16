"""
Unit tests for MachineState and FactoryState data models.

Tests creation, serialization (to_dict), LLM context formatting,
FactoryState extensions (conveyor, sensors, e-stop, error codes),
and error code interpretation.

Migrated from:
  - plc-client/tests/unit/test_models.py (V1)
  - plc-client-factoryio/tests/test_models.py (V2)
Adapted for V3 API: MachineState uses datetime timestamps and
fault_active (not fault_alarm), FactoryState adds conveyor/sensor/e-stop.
"""

import pytest
from datetime import datetime

from factorylm_plc.models import MachineState, FactoryState, ERROR_CODES


# ---------------------------------------------------------------------------
# MachineState
# ---------------------------------------------------------------------------


class TestMachineStateCreation:
    """Test MachineState instantiation and defaults."""

    def test_default_values(self):
        """Default MachineState has motor off, zero readings, no fault."""
        state = MachineState()
        assert state.motor_running is False
        assert state.motor_speed == 0
        assert state.motor_current == 0.0
        assert state.temperature == 0.0
        assert state.pressure == 0
        assert state.fault_active is False
        assert isinstance(state.timestamp, datetime)

    def test_custom_values(self):
        """Can create MachineState with custom values."""
        state = MachineState(
            motor_running=True,
            motor_speed=75,
            motor_current=2.5,
            temperature=45.0,
            pressure=120,
            fault_active=False,
        )
        assert state.motor_running is True
        assert state.motor_speed == 75
        assert state.motor_current == 2.5
        assert state.temperature == 45.0
        assert state.pressure == 120

    def test_timestamp_auto_set(self):
        """Timestamp defaults to approximately now."""
        before = datetime.now()
        state = MachineState()
        after = datetime.now()
        assert before <= state.timestamp <= after


class TestMachineStateSerialization:
    """Test to_dict serialization."""

    def test_to_dict_returns_dict(self):
        """to_dict returns a dict with all expected keys."""
        state = MachineState(
            motor_running=True,
            motor_speed=50,
            motor_current=1.5,
        )
        result = state.to_dict()

        assert isinstance(result, dict)
        assert result["motor_running"] is True
        assert result["motor_speed"] == 50
        assert result["motor_current"] == 1.5
        assert "timestamp" in result
        assert isinstance(result["timestamp"], str)  # ISO format string

    def test_to_dict_is_json_serializable(self):
        """to_dict output can be serialized to JSON."""
        import json

        state = MachineState(motor_running=True, motor_speed=80)
        data = state.to_dict()
        json_str = json.dumps(data)
        assert isinstance(json_str, str)

        parsed = json.loads(json_str)
        assert parsed["motor_speed"] == 80


class TestMachineStateLLMContext:
    """Test to_llm_context formatting for LLM prompts."""

    def test_running_context(self):
        """LLM context shows RUNNING with speed when motor is on."""
        state = MachineState(
            motor_running=True,
            motor_speed=75,
            motor_current=2.5,
            temperature=45.0,
            pressure=120,
        )
        context = state.to_llm_context()

        assert "RUNNING at 75%" in context
        assert "2.5A" in context
        assert "45.0C" in context
        assert "120 PSI" in context
        assert "None" in context  # No fault

    def test_stopped_context(self):
        """LLM context shows STOPPED without speed when motor is off."""
        state = MachineState(motor_running=False)
        context = state.to_llm_context()

        assert "STOPPED" in context
        assert "at " not in context


# ---------------------------------------------------------------------------
# FactoryState
# ---------------------------------------------------------------------------


class TestFactoryStateCreation:
    """Test FactoryState instantiation and extensions."""

    def test_extends_machine_state(self):
        """FactoryState inherits all MachineState fields."""
        state = FactoryState()
        assert hasattr(state, "motor_running")
        assert hasattr(state, "conveyor_running")
        assert hasattr(state, "e_stop_active")

    def test_factory_specific_defaults(self):
        """Factory I/O-specific fields have sensible defaults."""
        state = FactoryState()
        assert state.conveyor_speed == 0
        assert state.conveyor_running is False
        assert state.sensor_1_active is False
        assert state.sensor_2_active is False
        assert state.e_stop_active is False
        assert state.error_code == 0
        assert state.scene_name == "sorting_station"


class TestFactoryStateErrorCodes:
    """Test error code interpretation."""

    def test_known_error_codes(self):
        """All known error codes produce the expected message."""
        for code, message in ERROR_CODES.items():
            assert FactoryState.interpret_error_code(code) == message

    def test_unknown_error_code(self):
        """Unknown error code produces a descriptive fallback."""
        result = FactoryState.interpret_error_code(99)
        assert "Unknown error 99" in result

    def test_auto_error_message(self):
        """error_message is auto-populated from error_code via __post_init__."""
        state = FactoryState(error_code=2)
        assert state.error_message == "Temperature high"


class TestFactoryStateLLMContext:
    """Test FactoryState LLM context formatting."""

    def test_full_factory_context(self):
        """LLM context includes all Factory I/O fields."""
        state = FactoryState(
            motor_running=True,
            motor_speed=80,
            motor_current=3.0,
            temperature=55.0,
            pressure=110,
            conveyor_running=True,
            conveyor_speed=60,
            sensor_1_active=True,
            sensor_2_active=False,
            e_stop_active=False,
            error_code=0,
            scene_name="sorting_station",
        )
        context = state.to_llm_context()

        assert "RUNNING at 80%" in context
        assert "Conveyor: RUNNING at 60%" in context
        assert "S1=PART" in context
        assert "S2=clear" in context
        assert "E-Stop: Clear" in context
        assert "sorting_station" in context

    def test_estop_engaged_context(self):
        """LLM context highlights e-stop when engaged."""
        state = FactoryState(e_stop_active=True)
        context = state.to_llm_context()
        assert "ENGAGED!" in context

    def test_error_in_context(self):
        """LLM context shows error message when error_code is set."""
        state = FactoryState(error_code=3)
        context = state.to_llm_context()
        assert "Conveyor jam" in context


class TestFactoryStateSerialization:
    """Test FactoryState serialization."""

    def test_to_dict_includes_error_message(self):
        """to_dict includes the interpreted error_message."""
        state = FactoryState(error_code=1)
        result = state.to_dict()
        assert result["error_message"] == "Motor overload"
