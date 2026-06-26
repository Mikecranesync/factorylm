"""Tests for PLC-to-Hub canonical tag projection."""

from datetime import datetime, timezone

from factorylm_plc.modbus_tag_source import (
    REQUIRED_CANONICAL_TAGS,
    canonical_tag_name,
    canonical_tags_from_snapshot,
)
from factorylm_plc.models import TagSnapshot


def snapshot(**overrides):
    values = {
        "timestamp": datetime(2026, 6, 25, 12, 0, tzinfo=timezone.utc).isoformat(),
        "node_id": "plc-test",
        "motor_running": True,
        "motor_speed": 30,
        "motor_current": 4.5,
        "temperature": 31.2,
        "pressure": 100,
        "conveyor_running": True,
        "conveyor_speed": 30,
        "sensor_1": False,
        "sensor_2": False,
        "fault_alarm": False,
        "e_stop": False,
        "error_code": 0,
        "error_message": "No error",
        "coils": [0] * 18,
        "io": {
            "height_sensor_mm": 187,
            "sort_divert_active": True,
        },
        "e_stop_ok": True,
    }
    values.update(overrides)
    return TagSnapshot(**values)


def test_micro820_snapshot_maps_to_conveyor_canonical_tags():
    tags = canonical_tags_from_snapshot(snapshot())

    assert tags == {
        "conv_simple.motor_run": True,
        "conv_simple.vfd_speed_hz": 30,
        "conv_simple.vfd_current_amps": 4.5,
        "conv_simple.fault_code": 0,
        "conv_simple.comm_ok": True,
        "conv_simple.height_sensor_mm": 187,
        "conv_simple.sort_divert_active": True,
    }


def test_comm_fault_snapshot_marks_comm_not_ok_and_fault_code():
    tags = canonical_tags_from_snapshot(
        snapshot(motor_running=False, conveyor_running=False, motor_speed=0, error_code=5)
    )

    assert tags["conv_simple.motor_run"] is False
    assert tags["conv_simple.vfd_speed_hz"] == 0
    assert tags["conv_simple.fault_code"] == 5
    assert tags["conv_simple.comm_ok"] is False


def test_raw_stardust_tag_names_map_to_canonical_zone_tags():
    assert canonical_tag_name("Stardust/Launch 1/Block Occupied") == (
        "stardust.launch_1.block_occupied"
    )
    assert canonical_tag_name("Stardust.Launch2.LSM Ready") == (
        "stardust.launch_2.lsm_ready"
    )
    assert canonical_tag_name("stardust station load brake ready") == (
        "stardust.station_load.brake_ready"
    )
    assert canonical_tag_name("STARDUST_STATION_UNLOAD_FAULT_LATCHED") == (
        "stardust.station_unload.fault_latched"
    )


def test_raw_conveyor_tag_names_map_to_canonical_tags():
    assert canonical_tag_name("RunCommand") == "conv_simple.motor_run"
    assert canonical_tag_name("ConveyorHz") == "conv_simple.vfd_speed_hz"
    assert canonical_tag_name("MotorCurrentX10") == "conv_simple.vfd_current_amps"
    assert canonical_tag_name("ErrorCode") == "conv_simple.fault_code"
    assert canonical_tag_name("VFD_Comm_OK") == "conv_simple.comm_ok"
    assert canonical_tag_name("HeightSensorMm") == "conv_simple.height_sensor_mm"
    assert canonical_tag_name("SortDivertActive") == "conv_simple.sort_divert_active"


def test_required_canonical_tag_set_matches_task_contract():
    assert REQUIRED_CANONICAL_TAGS == frozenset(
        {
            "conv_simple.motor_run",
            "conv_simple.vfd_speed_hz",
            "conv_simple.vfd_current_amps",
            "conv_simple.fault_code",
            "conv_simple.comm_ok",
            "conv_simple.height_sensor_mm",
            "conv_simple.sort_divert_active",
            "stardust.launch_1.block_occupied",
            "stardust.launch_1.lsm_ready",
            "stardust.launch_1.brake_ready",
            "stardust.launch_1.fault_latched",
            "stardust.launch_2.block_occupied",
            "stardust.launch_2.lsm_ready",
            "stardust.launch_2.brake_ready",
            "stardust.launch_2.fault_latched",
            "stardust.station_load.block_occupied",
            "stardust.station_load.lsm_ready",
            "stardust.station_load.brake_ready",
            "stardust.station_load.fault_latched",
            "stardust.station_unload.block_occupied",
            "stardust.station_unload.lsm_ready",
            "stardust.station_unload.brake_ready",
            "stardust.station_unload.fault_latched",
        }
    )
