"""Week 5 tests — Downtime tracking: NLP classifier + API endpoints.

All tests use unittest.mock — no live DB or plc-modbus required.
Run: pytest tests/test_downtime.py -v

Acceptance Criteria (PRD-MES-CORE.md §10):
  AC#4  Downtime event captured within 10s of fault (covered by state_poller)
  AC#8  NLP classifier maps common phrases to correct reason codes
  AC#9  Manual reason entry updates open DOWN event
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.models.db_models import (
    DowntimeReason,
    DowntimeCategory,
    EnteredBy,
    Line,
    MachineState,
    MachineStateEnum,
)
from backend.services.downtime_classifier import classify_reason

# ── Fixtures ──────────────────────────────────────────────────────────────────

LINE_ID  = str(uuid.uuid4())
EVENT_ID = str(uuid.uuid4())
NOW      = datetime.now(timezone.utc)


def _make_line():
    line = MagicMock(spec=Line)
    line.id   = uuid.UUID(LINE_ID)
    line.name = "Conveyor-1"
    return line


def _make_reason(code: str, description: str, category: str = "UNPLANNED") -> DowntimeReason:
    r = MagicMock(spec=DowntimeReason)
    r.code        = code
    r.description = description
    r.category    = DowntimeCategory(category)
    return r


def _make_event(
    state: MachineStateEnum = MachineStateEnum.DOWN,
    reason_code: str = None,
    ended_at=None,
) -> MachineState:
    e = MagicMock(spec=MachineState)
    e.id          = uuid.UUID(EVENT_ID)
    e.line_id     = uuid.UUID(LINE_ID)
    e.state       = state
    e.reason_code = reason_code
    e.entered_by  = EnteredBy.PLC
    e.notes       = None
    e.started_at  = NOW
    e.ended_at    = ended_at
    return e


# ── NLP Classifier ────────────────────────────────────────────────────────────

class TestClassifyReason:
    # High-confidence hits
    def test_jam(self):
        code, conf = classify_reason("the conveyor is jammed")
        assert code == "JAM" and conf == "high"

    def test_estop(self):
        code, conf = classify_reason("emergency stop activated")
        assert code == "E_STOP" and conf == "high"

    def test_estop_hyphen(self):
        code, conf = classify_reason("e-stop was hit")
        assert code == "E_STOP" and conf == "high"

    def test_pm(self):
        code, conf = classify_reason("scheduled PM window")
        assert code == "MAINT_PM" and conf == "high"

    def test_preventive(self):
        code, conf = classify_reason("preventive maintenance")
        assert code == "MAINT_PM" and conf == "high"

    def test_breakdown(self):
        code, conf = classify_reason("machine broke down unexpectedly")
        assert code == "MAINT_BREAKDOWN" and conf == "high"

    def test_tooling(self):
        code, conf = classify_reason("tooling change on line 1")
        assert code == "CHANGEOVER_TOOLING" and conf == "high"

    def test_changeover(self):
        code, conf = classify_reason("product changeover to part B")
        assert code == "CHANGEOVER_PRODUCT" and conf == "high"

    def test_starved(self):
        code, conf = classify_reason("line is starved, no material")
        assert code == "STARVED_MATERIAL" and conf == "high"

    def test_blocked(self):
        code, conf = classify_reason("downstream is blocked")
        assert code == "BLOCKED_DOWNSTREAM" and conf == "high"

    def test_quality_hold(self):
        code, conf = classify_reason("quality hold for inspection")
        assert code == "QUALITY_HOLD" and conf == "high"

    def test_overload(self):
        code, conf = classify_reason("motor overload tripped")
        assert code == "OVERLOAD" and conf == "high"

    def test_overheat(self):
        code, conf = classify_reason("drive is overheating")
        assert code == "OVERHEAT" and conf == "high"

    def test_sensor(self):
        code, conf = classify_reason("proximity sensor failed")
        assert code == "SENSOR_FAIL" and conf == "high"

    def test_comms(self):
        code, conf = classify_reason("modbus timeout — comms lost")
        assert code == "COMMS_FAIL" and conf == "high"

    # Fallback
    def test_unknown_fallback(self):
        code, conf = classify_reason("something weird happened on the floor")
        assert code == "UNKNOWN" and conf == "low"

    def test_empty_string_fallback(self):
        code, conf = classify_reason("")
        assert code == "UNKNOWN" and conf == "low"

    def test_none_safe(self):
        code, conf = classify_reason(None)
        assert code == "UNKNOWN" and conf == "low"

    # Priority: E_STOP beats breakdown
    def test_estop_priority_over_breakdown(self):
        code, conf = classify_reason("e-stop triggered, motor fault")
        assert code == "E_STOP" and conf == "high"

    # Case insensitive
    def test_case_insensitive(self):
        code, conf = classify_reason("JAM IN THE FEEDER")
        assert code == "JAM" and conf == "high"


# ── Downtime API (via TestClient + mocked DB) ─────────────────────────────────

@pytest.fixture()
def client():
    from backend.database import get_db
    mock_db = MagicMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c, mock_db
    app.dependency_overrides.clear()


class TestListDowntimeReasons:
    def test_returns_200_list(self, client):
        tc, db = client
        db.query.return_value.order_by.return_value.all.return_value = [
            _make_reason("JAM", "Conveyor or mechanism jam"),
            _make_reason("MAINT_PM", "Planned preventive maintenance", "PLANNED"),
        ]
        resp = tc.get("/api/mes/downtime-reasons")
        assert resp.status_code == 200
        assert len(resp.json()) == 2


class TestGetLineDowntime:
    def test_returns_200_list(self, client):
        tc, db = client
        db.query.return_value.filter.return_value.first.return_value = _make_line()
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            _make_event(MachineStateEnum.DOWN, "JAM"),
        ]
        # second query for DowntimeReason join
        db.query.return_value.filter.return_value.first.side_effect = [
            _make_line(),
            _make_reason("JAM", "Conveyor or mechanism jam"),
        ]
        resp = tc.get(f"/api/mes/lines/{LINE_ID}/downtime")
        assert resp.status_code == 200

    def test_unknown_line_returns_404(self, client):
        tc, db = client
        db.query.return_value.filter.return_value.first.return_value = None
        resp = tc.get(f"/api/mes/lines/{LINE_ID}/downtime")
        assert resp.status_code == 404


class TestEnterDowntimeReason:
    def test_direct_reason_code_succeeds(self, client):
        tc, db = client
        event = _make_event(MachineStateEnum.DOWN, None)
        reason = _make_reason("JAM", "Conveyor or mechanism jam")
        db.query.return_value.filter.return_value.first.side_effect = [
            _make_line(),              # line lookup
            event,                     # open DOWN event
            reason,                    # validate reason_code
            reason,                    # final reason join
        ]
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = event
        db.refresh.side_effect = lambda obj: None

        resp = tc.post(f"/api/mes/lines/{LINE_ID}/downtime", json={
            "reason_code": "JAM",
            "entered_by":  "OPERATOR",
        })
        assert resp.status_code == 200
        assert resp.json()["event"]["reason_code"] == "JAM"

    def test_nlp_description_classifies_and_succeeds(self, client):
        tc, db = client
        event  = _make_event(MachineStateEnum.DOWN, None)
        reason = _make_reason("JAM", "Conveyor or mechanism jam")
        # Line lookup → filter().first(); open event → order_by().first()
        # NLP path: no reason validation query; final reason join → filter().first()
        db.query.return_value.filter.return_value.first.side_effect = [
            _make_line(),
            reason,   # final reason join after NLP classify
        ]
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = event
        db.refresh.side_effect = lambda obj: None

        resp = tc.post(f"/api/mes/lines/{LINE_ID}/downtime", json={
            "description": "the conveyor is jammed",
            "entered_by":  "MIRA_AI",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["classified"] is True
        assert data["confidence"] == "high"

    def test_no_open_event_returns_409(self, client):
        tc, db = client
        db.query.return_value.filter.return_value.first.return_value = _make_line()
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
        resp = tc.post(f"/api/mes/lines/{LINE_ID}/downtime", json={
            "reason_code": "JAM",
            "entered_by":  "OPERATOR",
        })
        assert resp.status_code == 409

    def test_unknown_reason_code_returns_422(self, client):
        tc, db = client
        event = _make_event(MachineStateEnum.DOWN, None)
        # Line → filter().first(); open event → order_by().first(); reason lookup → filter().first() = None
        db.query.return_value.filter.return_value.first.side_effect = [
            _make_line(),
            None,  # reason_code not found in downtime_reasons
        ]
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = event
        resp = tc.post(f"/api/mes/lines/{LINE_ID}/downtime", json={
            "reason_code": "MADE_UP_CODE",
            "entered_by":  "OPERATOR",
        })
        assert resp.status_code == 422

    def test_missing_both_fields_returns_422(self, client):
        tc, db = client
        db.query.return_value.filter.return_value.first.side_effect = [
            _make_line(),
            _make_event(MachineStateEnum.DOWN, None),
        ]
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = _make_event()
        resp = tc.post(f"/api/mes/lines/{LINE_ID}/downtime", json={
            "entered_by": "OPERATOR",
        })
        assert resp.status_code == 422

    def test_unknown_line_returns_404(self, client):
        tc, db = client
        db.query.return_value.filter.return_value.first.return_value = None
        resp = tc.post(f"/api/mes/lines/{LINE_ID}/downtime", json={
            "reason_code": "JAM",
            "entered_by":  "OPERATOR",
        })
        assert resp.status_code == 404
