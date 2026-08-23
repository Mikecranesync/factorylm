"""Week 6 tests — Atlas CMMS bidirectional sync.

All tests use unittest.mock — no live DB, no GitHub API calls.
Run: pytest tests/test_cmms.py -v

Acceptance Criteria (PRD-MES-CORE.md §10):
  AC#9  Work order created in CMMS appears in /api/mes/work-orders (ingest)
  AC#10 Work order created via API appears in CMMS (sync push)
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.models.db_models import Line, Product, WorkOrder, WorkOrderStatus
from backend.services.cmms_client import format_work_order

# ── Fixtures ──────────────────────────────────────────────────────────────────

LINE_ID    = str(uuid.uuid4())
PRODUCT_ID = str(uuid.uuid4())
WO_ID      = str(uuid.uuid4())
NOW        = datetime.now(timezone.utc)


def _make_line(name: str = "Conveyor-1") -> Line:
    line = MagicMock(spec=Line)
    line.id          = uuid.UUID(LINE_ID)
    line.name        = name
    line.isa95_path  = "lakewales/floor/conveyor-1"
    line.description = "Main conveyor"
    return line


def _make_product(sku: str = "SKU-001") -> Product:
    p = MagicMock(spec=Product)
    p.id              = uuid.UUID(PRODUCT_ID)
    p.sku             = sku
    p.name            = "Widget A"
    p.ideal_cycle_sec = 2.0
    return p


def _make_wo(
    status: WorkOrderStatus = WorkOrderStatus.PENDING,
    cmms_ref: str = None,
) -> WorkOrder:
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
    wo.cmms_ref        = cmms_ref
    wo.cmms_synced_at  = NOW if cmms_ref else None
    wo.created_at      = NOW
    return wo


@pytest.fixture()
def client():
    from backend.database import get_db
    mock_db = MagicMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c, mock_db
    app.dependency_overrides.clear()


# ── format_work_order (pure function) ─────────────────────────────────────────

class TestFormatWorkOrder:
    def test_maps_all_required_fields(self):
        meta = format_work_order(
            order_number="WO-001",
            status="ACTIVE",
            target_qty=100,
            good_qty=80,
            line_name="Conveyor-1",
            line_isa95_path="lakewales/floor/conveyor-1",
            product_sku="SKU-001",
            product_name="Widget A",
        )
        assert meta["work_order_id"] == "WO-001"
        assert meta["status"]        == "active"
        assert meta["asset_name"]    == "Conveyor-1"
        assert meta["cmms_system"]   == "FactoryLM MES"
        assert "Widget A" in meta["title"]
        assert "Conveyor-1" in meta["title"]

    def test_description_includes_qty(self):
        meta = format_work_order(
            order_number="WO-002", status="PENDING",
            target_qty=200, good_qty=0,
            line_name="Sorting-1", line_isa95_path="lakewales/floor/sorting-1",
            product_sku="SKU-002", product_name="Bolt B",
        )
        assert "200" in meta["description"]
        assert "SKU-002" in meta["description"]

    def test_notes_in_completion_notes(self):
        meta = format_work_order(
            order_number="WO-003", status="COMPLETE",
            target_qty=50, good_qty=50,
            line_name="L1", line_isa95_path="lw/floor/l1",
            product_sku="SKU-003", product_name="Part C",
            notes="All good, no issues",
        )
        assert meta["completion_notes"] == "All good, no issues"

    def test_completed_date_populated_when_actual_end_given(self):
        end = datetime(2026, 4, 16, 12, 0, 0, tzinfo=timezone.utc)
        meta = format_work_order(
            order_number="WO-004", status="COMPLETE",
            target_qty=50, good_qty=50,
            line_name="L1", line_isa95_path="lw/floor/l1",
            product_sku="SKU-004", product_name="Part D",
            actual_end=end,
        )
        assert "2026-04-16" in meta["completed_date"]

    def test_empty_completed_date_when_no_actual_end(self):
        meta = format_work_order(
            order_number="WO-005", status="ACTIVE",
            target_qty=50, good_qty=0,
            line_name="L1", line_isa95_path="lw/floor/l1",
            product_sku="SKU-005", product_name="Part E",
        )
        assert meta["completed_date"] == ""


# ── push_work_order: disabled mode (no HTTP) ──────────────────────────────────

class TestPushWorkOrderDisabled:
    def test_returns_synthetic_gist_when_disabled(self):
        """cmms_enabled=False → synthetic response, no HTTP call."""
        from backend.services.cmms_client import push_work_order
        meta = format_work_order(
            order_number="WO-100", status="PENDING",
            target_qty=10, good_qty=0,
            line_name="L1", line_isa95_path="lw/floor/l1",
            product_sku="SKU-100", product_name="Thing",
        )
        result = push_work_order(meta)  # cmms_enabled=False by default in test env
        assert "gist_id"  in result
        assert "gist_url" in result
        assert "gist.github.com" in result["gist_url"]

    def test_uses_existing_gist_id_in_synthetic_response(self):
        from backend.services.cmms_client import push_work_order
        meta = format_work_order(
            order_number="WO-101", status="ACTIVE",
            target_qty=10, good_qty=5,
            line_name="L1", line_isa95_path="lw/floor/l1",
            product_sku="SKU-101", product_name="Thing",
        )
        result = push_work_order(meta, gist_id="existing123")
        assert result["gist_id"] == "existing123"


# ── CMMS API endpoints ────────────────────────────────────────────────────────

class TestSyncEndpoint:
    def test_sync_returns_200_with_gist_url(self, client):
        tc, db = client
        wo      = _make_wo()
        line    = _make_line()
        product = _make_product()
        db.query.return_value.filter.return_value.first.side_effect = [
            wo, line, product,
        ]
        db.refresh.side_effect = lambda obj: None

        resp = tc.post(f"/api/mes/cmms/sync/{WO_ID}")
        assert resp.status_code == 200
        data = resp.json()
        assert "gist_id"  in data
        assert "gist_url" in data
        assert data["order_number"] == "WO-001"

    def test_sync_unknown_wo_returns_404(self, client):
        tc, db = client
        db.query.return_value.filter.return_value.first.return_value = None
        resp = tc.post(f"/api/mes/cmms/sync/{WO_ID}")
        assert resp.status_code == 404

    def test_sync_updates_existing_gist(self, client):
        """If cmms_ref already set, push uses the existing Gist ID."""
        tc, db = client
        wo = _make_wo(cmms_ref="existing-gist-abc")
        db.query.return_value.filter.return_value.first.side_effect = [
            wo, _make_line(), _make_product(),
        ]
        db.refresh.side_effect = lambda obj: None

        resp = tc.post(f"/api/mes/cmms/sync/{WO_ID}")
        assert resp.status_code == 200
        # Should carry through the existing gist_id in synthetic mode
        assert resp.json()["gist_id"] == "existing-gist-abc"


class TestSyncStatusEndpoint:
    def test_unsynced_wo_returns_synced_false(self, client):
        tc, db = client
        db.query.return_value.filter.return_value.first.return_value = _make_wo()
        resp = tc.get(f"/api/mes/cmms/sync/{WO_ID}")
        assert resp.status_code == 200
        assert resp.json()["synced"] is False
        assert resp.json()["cmms_ref"] is None

    def test_synced_wo_returns_synced_true(self, client):
        tc, db = client
        db.query.return_value.filter.return_value.first.return_value = _make_wo(
            cmms_ref="abc123"
        )
        resp = tc.get(f"/api/mes/cmms/sync/{WO_ID}")
        assert resp.status_code == 200
        assert resp.json()["synced"] is True
        assert resp.json()["cmms_ref"] == "abc123"

    def test_unknown_wo_returns_404(self, client):
        tc, db = client
        db.query.return_value.filter.return_value.first.return_value = None
        resp = tc.get(f"/api/mes/cmms/sync/{WO_ID}")
        assert resp.status_code == 404


class TestIngestEndpoint:
    def test_ingest_creates_wo_from_cmms(self, client):
        tc, db = client
        wo = _make_wo()
        db.query.return_value.filter.return_value.first.side_effect = [
            None,           # order_number unique check (not exists)
            _make_line(),   # line by name
            _make_product(), # product by sku
        ]
        db.refresh.side_effect = lambda obj: None

        with patch("backend.routes.cmms.WorkOrder", return_value=wo):
            resp = tc.post("/api/mes/cmms/ingest", json={
                "order_number": "WO-CMMS-001",
                "product_sku":  "SKU-001",
                "line_name":    "Conveyor-1",
                "target_qty":   100,
                "cmms_ref":     "gist-abc123",
            })
        assert resp.status_code == 201

    def test_ingest_idempotent_on_duplicate_order_number(self, client):
        tc, db = client
        existing_wo = _make_wo()
        db.query.return_value.filter.return_value.first.return_value = existing_wo
        resp = tc.post("/api/mes/cmms/ingest", json={
            "order_number": "WO-001",
            "product_sku":  "SKU-001",
            "line_name":    "Conveyor-1",
            "target_qty":   100,
        })
        # Should return 201 with the existing WO, not error
        assert resp.status_code == 201

    def test_ingest_unknown_line_returns_404(self, client):
        tc, db = client
        db.query.return_value.filter.return_value.first.side_effect = [
            None,  # order_number not exists
            None,  # line not found
        ]
        resp = tc.post("/api/mes/cmms/ingest", json={
            "order_number": "WO-999",
            "product_sku":  "SKU-001",
            "line_name":    "NonExistentLine",
            "target_qty":   50,
        })
        assert resp.status_code == 404

    def test_ingest_unknown_product_returns_404(self, client):
        tc, db = client
        db.query.return_value.filter.return_value.first.side_effect = [
            None,           # order_number not exists
            _make_line(),   # line found
            None,           # product not found
        ]
        resp = tc.post("/api/mes/cmms/ingest", json={
            "order_number": "WO-998",
            "product_sku":  "SKU-GHOST",
            "line_name":    "Conveyor-1",
            "target_qty":   50,
        })
        assert resp.status_code == 404
