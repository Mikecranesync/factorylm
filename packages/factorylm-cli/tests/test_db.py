"""Tests for the SQLite tag store."""

import json

from factorylm.db.store import TagStore


def test_insert_and_get(tmp_path):
    store = TagStore(db_path=str(tmp_path / "test.db"))
    tag_id = store.insert_tags({"motor_speed": 42, "temperature": 23.5})
    assert tag_id == 1

    rows = store.get_latest(1)
    assert len(rows) == 1
    assert rows[0]["tags"]["motor_speed"] == 42
    assert rows[0]["tags"]["temperature"] == 23.5


def test_latest_tags(tmp_path):
    store = TagStore(db_path=str(tmp_path / "test.db"))
    store.insert_tags({"motor_speed": 10})
    store.insert_tags({"motor_speed": 20})
    tags = store.get_latest_tags()
    assert tags["motor_speed"] == 20


def test_fault_creates_incident(tmp_path):
    store = TagStore(db_path=str(tmp_path / "test.db"))
    store.insert_tags({"fault_alarm": True, "error_code": 3, "error_message": "Conveyor jam"})

    incidents = store.get_incidents(status="open")
    assert len(incidents) == 1
    assert incidents[0]["error_code"] == 3
    assert incidents[0]["error_message"] == "Conveyor jam"


def test_e_stop_creates_incident(tmp_path):
    store = TagStore(db_path=str(tmp_path / "test.db"))
    store.insert_tags({"e_stop": True})

    incidents = store.get_incidents(status="open")
    assert len(incidents) == 1
    assert incidents[0]["error_code"] == -1


def test_no_duplicate_incidents(tmp_path):
    store = TagStore(db_path=str(tmp_path / "test.db"))
    store.insert_tags({"fault_alarm": True, "error_code": 1})
    store.insert_tags({"fault_alarm": True, "error_code": 1})

    incidents = store.get_incidents(status="open")
    assert len(incidents) == 1


def test_insert_insight(tmp_path):
    store = TagStore(db_path=str(tmp_path / "test.db"))
    store.insert_tags({"fault_alarm": True, "error_code": 1})
    incidents = store.get_incidents(status="open")
    inc_id = incidents[0]["id"]

    insight_id = store.insert_insight(
        incident_id=inc_id,
        summary="Motor overload",
        root_cause="Bearing failure",
        confidence=0.85,
        reasoning="Current too high",
        suggested_checks=["Check bearings"],
        cosmos_model="test",
    )
    assert insight_id >= 1

    # Incident should be marked as analyzed
    analyzed = store.get_incidents(status="analyzed")
    assert len(analyzed) == 1


def test_flat_snapshots(tmp_path):
    store = TagStore(db_path=str(tmp_path / "test.db"))
    store.insert_tags({"motor_speed": 55, "temperature": 30.0})

    flat = store.get_snapshots_as_flat(10)
    assert len(flat) == 1
    assert flat[0]["motor_speed"] == 55
    assert "id" in flat[0]
    assert "timestamp" in flat[0]
