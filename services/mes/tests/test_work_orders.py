"""Week 4 tests — Work order CRUD, status transitions, and schedule-aware TEEP.

All tests use unittest.mock — no live DB or plc-modbus required.
Run: pytest tests/test_work_orders.py -v

Acceptance Criteria (PRD-MES-CORE.md §10):
  AC#6  Work orders create / transition without errors
  AC#7  One ACTIVE work order per line enforced
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.models.db_models import Line, Product, WorkOrder, WorkOrderStatus
from backend.services.oee_calculator import compute_oee

# ── Fixtures ──────────────────────────────────────────────────────────────────

LINE_ID    = str(uuid.uuid4())
PRODUCT_ID = str(uuid.uuid4())
WO_ID      = str(uuid.uuid4())

NOW = datetime.now(timezone.utc)


def _make_line():
    line = MagicMock(spec=Line)
    line.id   = uuid.UUID(LINE_ID)
    line.name = "Conveyor-1"
    return line


def _make_product(ideal_cycle_sec: float = 2.0):
    p = MagicMock(spec=Product)
    p.id              = uuid.UUID(PRODUCT_ID)
    p.sku             = "SKU-001"
    p.name            = "Widget A"
    p.ideal_cycle_sec = ideal_cycle_sec
    p.description     = None
    return p


def _make_wo(status: WorkOrderStatus = WorkOrderStatus.PENDING):
    wo = MagicMock(spec=WorkOrder)
    wo.id              = uuid.UUID(WO_ID)
    wo.order_number    = "WO-001"
    wo.product_id      = uuid.UUID(PRODUCT_ID)
    wo.line_id         = uuid.UUID(LINE_ID)
    wo.target_qty      = 100
    wo.good_qty        = 0
    wo.status          = status
    wo.scheduled_start = None
    wo.actual_start    = None
    wo.actual_end      = None
    wo.notes           = None
    wo.created_at      = NOW
    return wo


# ── compute_oee: utilisation param (TEEP) ─────────────────────────────────────

class TestComputeOEEUtilisation:
    def test_teep_equals_oee_when_utilisation_1(self):
        """Default utilisation=1.0 → TEEP == OEE (Week 3 behaviour preserved)."""
        m = compute_oee(
            run_time_sec=48, planned_time_sec=60,
            total_count=40, good_count=38, ideal_cycle_sec=1.0,
        )
        assert m["teep"] == pytest.approx(m["oee"], abs=0.001)

    def test_teep_scaled_by_utilisation(self):
        """utilisation=0.5 → TEEP = OEE × 0.5"""
        m = compute_oee(
            run_time_sec=60, planned_time_sec=60,
            total_count=60, good_count=60, ideal_cycle_sec=1.0,
            utilisation=0.5,
        )
        assert m["oee"]  == pytest.approx(1.0,  abs=0.001)
        assert m["teep"] == pytest.approx(0.5,  abs=0.001)

    def test_teep_zero_when_outside_schedule(self):
        """utilisation=0.0 → TEEP = 0 (line running outside shift)."""
        m = compute_oee(
            run_time_sec=60, planned_time_sec=60,
            total_count=60, good_count=60, ideal_cycle_sec=1.0,
            utilisation=0.0,
        )
        assert m["oee"]  == pytest.approx(1.0, abs=0.001)
        assert m["teep"] == 0.0

    def test_teep_clamped_to_1(self):
        """utilisation > 1.0 is clamped — TEEP never exceeds 1.0."""
        m = compute_oee(
            run_time_sec=60, planned_time_sec=60,
            total_count=60, good_count=60, ideal_cycle_sec=1.0,
            utilisation=2.0,
        )
        assert m["teep"] == pytest.approx(1.0, abs=0.001)

    def test_teep_rounded_to_4_decimals(self):
        m = compute_oee(48, 60, 40, 38, 1.0, utilisation=0.75)
        assert m["teep"] == round(m["teep"], 4)


# ── Work order API (via TestClient + mocked DB) ────────────────────────────────

@pytest.fixture()
def client():
    """FastAPI test client with DB dependency overridden."""
    from backend.database import get_db

    mock_db = MagicMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c, mock_db
    app.dependency_overrides.clear()


class TestCreateWorkOrder:
    def test_create_returns_201(self, client):
        tc, db = client
        db.query.return_value.filter.return_value.first.side_effect = [
            _make_line(),    # line exists
            _make_product(), # product exists
            None,            # order_number unique check
        ]
        wo = _make_wo()
        db.refresh.side_effect = lambda obj: None

        with patch("backend.routes.work_orders.WorkOrder", return_value=wo):
            resp = tc.post("/api/mes/work-orders", json={
                "order_number": "WO-001",
                "product_id":   PRODUCT_ID,
                "line_id":      LINE_ID,
                "target_qty":   100,
            })

        assert resp.status_code == 201
        assert resp.json()["order_number"] == "WO-001"

    def test_create_missing_line_returns_404(self, client):
        tc, db = client
        db.query.return_value.filter.return_value.first.return_value = None  # line not found
        resp = tc.post("/api/mes/work-orders", json={
            "order_number": "WO-002",
            "product_id":   PRODUCT_ID,
            "line_id":      LINE_ID,
            "target_qty":   50,
        })
        assert resp.status_code == 404

    def test_duplicate_order_number_returns_409(self, client):
        tc, db = client
        db.query.return_value.filter.return_value.first.side_effect = [
            _make_line(),    # line exists
            _make_product(), # product exists
            _make_wo(),      # duplicate order_number
        ]
        resp = tc.post("/api/mes/work-orders", json={
            "order_number": "WO-001",
            "product_id":   PRODUCT_ID,
            "line_id":      LINE_ID,
            "target_qty":   100,
        })
        assert resp.status_code == 409


class TestListWorkOrders:
    def test_list_returns_200(self, client):
        tc, db = client
        db.query.return_value.order_by.return_value.all.return_value = [_make_wo()]
        # No filters applied — query chain has no .filter()
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [_make_wo()]
        resp = tc.get("/api/mes/work-orders")
        assert resp.status_code == 200

    def test_invalid_status_filter_returns_422(self, client):
        tc, db = client
        resp = tc.get("/api/mes/work-orders?status=BOGUS")
        assert resp.status_code == 422


class TestGetWorkOrder:
    def test_found_returns_200(self, client):
        tc, db = client
        db.query.return_value.filter.return_value.first.return_value = _make_wo()
        resp = tc.get(f"/api/mes/work-orders/{WO_ID}")
        assert resp.status_code == 200
        assert resp.json()["id"] == WO_ID

    def test_not_found_returns_404(self, client):
        tc, db = client
        db.query.return_value.filter.return_value.first.return_value = None
        resp = tc.get(f"/api/mes/work-orders/{WO_ID}")
        assert resp.status_code == 404


class TestStatusTransitions:
    def test_pending_to_active(self, client):
        tc, db = client
        wo = _make_wo(WorkOrderStatus.PENDING)
        db.query.return_value.filter.return_value.first.side_effect = [
            wo,   # fetch the WO
            None, # no conflicting ACTIVE on this line
        ]
        db.refresh.side_effect = lambda obj: None
        resp = tc.patch(f"/api/mes/work-orders/{WO_ID}/status", json={"status": "ACTIVE"})
        assert resp.status_code == 200

    def test_complete_to_any_is_invalid(self, client):
        tc, db = client
        wo = _make_wo(WorkOrderStatus.COMPLETE)
        db.query.return_value.filter.return_value.first.return_value = wo
        resp = tc.patch(f"/api/mes/work-orders/{WO_ID}/status", json={"status": "ACTIVE"})
        assert resp.status_code == 422

    def test_second_active_on_same_line_returns_409(self, client):
        tc, db = client
        wo = _make_wo(WorkOrderStatus.PENDING)
        conflict = _make_wo(WorkOrderStatus.ACTIVE)
        conflict.id = uuid.UUID(str(uuid.uuid4()))
        db.query.return_value.filter.return_value.first.side_effect = [
            wo,       # fetch the WO
            conflict, # conflicting ACTIVE WO
        ]
        resp = tc.patch(f"/api/mes/work-orders/{WO_ID}/status", json={"status": "ACTIVE"})
        assert resp.status_code == 409

    def test_unknown_status_value_returns_422(self, client):
        tc, db = client
        wo = _make_wo(WorkOrderStatus.PENDING)
        db.query.return_value.filter.return_value.first.return_value = wo
        resp = tc.patch(f"/api/mes/work-orders/{WO_ID}/status", json={"status": "LAUNCHED"})
        assert resp.status_code == 422


# ── Product endpoints ──────────────────────────────────────────────────────────

class TestProducts:
    def test_create_product_returns_201(self, client):
        tc, db = client
        db.query.return_value.filter.return_value.first.return_value = None  # no duplicate
        p = _make_product()
        db.refresh.side_effect = lambda obj: None

        with patch("backend.routes.work_orders.Product", return_value=p):
            resp = tc.post("/api/mes/products", json={
                "sku": "SKU-001",
                "name": "Widget A",
                "ideal_cycle_sec": 2.0,
            })
        assert resp.status_code == 201

    def test_duplicate_sku_returns_409(self, client):
        tc, db = client
        db.query.return_value.filter.return_value.first.return_value = _make_product()
        resp = tc.post("/api/mes/products", json={
            "sku": "SKU-001",
            "name": "Widget A",
            "ideal_cycle_sec": 2.0,
        })
        assert resp.status_code == 409
