"""Smoke tests for the Telegram I/O adapter module."""

import pytest

from io_adapter import (
    PLCIOReader,
    format_io,
    is_factory_question,
    FACTORY_KEYWORDS,
    PLC_API_URL,
)


# ---------------------------------------------------------------------------
# URL sanity
# ---------------------------------------------------------------------------


class TestConfig:
    def test_plc_api_url_points_to_plc_laptop(self):
        assert "100.72.2.99" in PLC_API_URL, (
            f"PLC_API_URL should reference the PLC laptop IP, got {PLC_API_URL}"
        )

    def test_factory_keywords_non_empty(self):
        assert len(FACTORY_KEYWORDS) > 0


# ---------------------------------------------------------------------------
# is_factory_question
# ---------------------------------------------------------------------------


class TestFactoryQuestionDetection:
    @pytest.mark.parametrize("text", [
        "What's the motor status?",
        "Is the conveyor running?",
        "Check the PLC readings",
        "Any fault alarms?",
        "What's the temperature and pressure?",
        "Diagnose the machine",
        "factory floor update",
        "sensor 1 triggered?",
    ])
    def test_detects_factory_questions(self, text):
        assert is_factory_question(text) is True

    @pytest.mark.parametrize("text", [
        "Hello how are you?",
        "What time is it?",
        "Tell me a joke",
        "Deploy to production",
        "",
    ])
    def test_rejects_non_factory_questions(self, text):
        assert is_factory_question(text) is False


# ---------------------------------------------------------------------------
# format_io
# ---------------------------------------------------------------------------


SAMPLE_IO = {
    "coils": {
        "motor_running": True,
        "motor_stopped": False,
        "fault_alarm": False,
        "conveyor_running": True,
        "sensor_1_active": False,
        "sensor_2_active": False,
        "e_stop_active": False,
    },
    "inputs": {"DI_00": False, "DI_01": False},
    "outputs": {"DO_00": True, "DO_01": False},
    "registers": {
        "motor_speed": 1750,
        "motor_current": 4.2,
        "temperature": 42,
        "pressure": 95,
        "conveyor_speed": 30,
        "error_code": 0,
    },
}

SAMPLE_VFD = {
    "running": True,
    "direction": "FWD",
    "frequency_hz": 30.0,
    "current_a": 2.5,
    "rpm": 1750,
    "voltage_v": 230,
    "temp_c": 38,
    "fault": False,
    "fault_desc": "None",
    "ready": True,
}


class TestFormatIO:
    def test_basic_format_returns_string(self):
        result = format_io(SAMPLE_IO)
        assert isinstance(result, str)
        assert "Factory Status" in result

    def test_motor_running_shown(self):
        result = format_io(SAMPLE_IO)
        assert "RUNNING" in result

    def test_motor_stopped(self):
        stopped = {**SAMPLE_IO, "coils": {**SAMPLE_IO["coils"], "motor_running": False}}
        result = format_io(stopped)
        assert "STOPPED" in result

    def test_fault_alarm_shown(self):
        fault = {**SAMPLE_IO, "coils": {**SAMPLE_IO["coils"], "fault_alarm": True}}
        result = format_io(fault)
        assert "FAULT ALARM" in result

    def test_estop_shown(self):
        estop = {**SAMPLE_IO, "coils": {**SAMPLE_IO["coils"], "e_stop_active": True}}
        result = format_io(estop)
        assert "ACTIVE" in result

    def test_nominal_message_when_no_faults(self):
        result = format_io(SAMPLE_IO)
        assert "nominal" in result.lower()

    def test_warning_when_faults(self):
        fault = {**SAMPLE_IO, "coils": {**SAMPLE_IO["coils"], "fault_alarm": True}}
        result = format_io(fault)
        assert "WARNING" in result or "Check" in result

    def test_vfd_section_included(self):
        result = format_io(SAMPLE_IO, SAMPLE_VFD)
        assert "VFD" in result
        assert "GS10" in result
        assert "30" in result  # frequency_hz

    def test_vfd_fault_shown(self):
        vfd_fault = {**SAMPLE_VFD, "fault": True, "fault_desc": "Overcurrent"}
        result = format_io(SAMPLE_IO, vfd_fault)
        assert "Overcurrent" in result

    def test_no_vfd_when_none(self):
        result = format_io(SAMPLE_IO, None)
        assert "VFD" not in result

    def test_empty_io_data(self):
        result = format_io({"coils": {}, "inputs": {}, "outputs": {}, "registers": {}})
        assert "Factory Status" in result

    def test_readings_shown(self):
        result = format_io(SAMPLE_IO)
        assert "1750" in result  # motor speed
        assert "95" in result  # pressure


# ---------------------------------------------------------------------------
# PLCIOReader construction
# ---------------------------------------------------------------------------


class TestPLCIOReader:
    def test_default_url(self):
        reader = PLCIOReader()
        assert "100.72.2.99" in reader.base_url

    def test_custom_url(self):
        reader = PLCIOReader(base_url="http://10.0.0.1:9000/")
        assert reader.base_url == "http://10.0.0.1:9000"  # trailing slash stripped
