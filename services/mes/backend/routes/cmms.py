"""CMMS sync routes — bidirectional work order sync via GitHub Gist.

Week 6 endpoints:
  POST /api/mes/cmms/sync/{work_order_id}  — push WO to CMMS Gist
  GET  /api/mes/cmms/sync/{work_order_id}  — sync status (cmms_ref, ts)
  POST /api/mes/cmms/ingest                — import CMMS work order → MES

Controlled by settings.cmms_enabled:
  False (default) — push returns a synthetic Gist reference, no HTTP calls.
  True            — calls GitHub Gist API with settings.cmms_github_token.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.db_models import Line, Product, WorkOrder, WorkOrderStatus
from backend.models.mes_models import WorkOrderResponse
from backend.routes.work_orders import _to_response
from backend.services import cmms_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mes/cmms", tags=["cmms"])


# ── Response models ───────────────────────────────────────────────────────────

class CMMSSyncStatus(BaseModel):
    work_order_id:  str
    order_number:   str
    cmms_ref:       Optional[str]   # Gist ID, None if never synced
    cmms_gist_url:  Optional[str]
    cmms_synced_at: Optional[datetime]
    synced:         bool


class CMMSSyncResult(BaseModel):
    work_order_id:  str
    order_number:   str
    gist_id:        str
    gist_url:       str
    cmms_synced_at: datetime


class CMMSIngestRequest(BaseModel):
    """Inbound CMMS work order — resolves product by SKU, line by name."""
    order_number:    str
    product_sku:     str
    line_name:       str
    target_qty:      int = Field(gt=0)
    notes:           Optional[str] = None
    cmms_ref:        Optional[str] = None   # Gist ID if already exists in CMMS


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/sync/{work_order_id}", response_model=CMMSSyncResult)
def sync_work_order_to_cmms(work_order_id: str, db: Session = Depends(get_db)):
    """Push a MES work order to CMMS (creates or updates Gist).

    Saves the returned Gist ID back to work_orders.cmms_ref.
    Safe to call multiple times — updates the existing Gist on repeat.
    """
    wo = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    if not wo:
        raise HTTPException(status_code=404, detail=f"Work order '{work_order_id}' not found")

    line    = db.query(Line).filter(Line.id == wo.line_id).first()
    product = db.query(Product).filter(Product.id == wo.product_id).first()

    metadata = cmms_client.format_work_order(
        order_number=wo.order_number,
        status=wo.status.value,
        target_qty=wo.target_qty,
        good_qty=wo.good_qty,
        line_name=line.name if line else "Unknown",
        line_isa95_path=line.isa95_path if line else "",
        product_sku=product.sku if product else "",
        product_name=product.name if product else "Unknown",
        notes=wo.notes,
        actual_start=wo.actual_start,
        actual_end=wo.actual_end,
        cmms_external_id=wo.cmms_ref,
    )

    try:
        result = cmms_client.push_work_order(metadata, gist_id=wo.cmms_ref)
    except Exception as exc:
        logger.exception("CMMS push failed for WO %s", wo.order_number)
        raise HTTPException(status_code=502, detail=f"CMMS push failed: {exc}") from exc

    # Persist Gist reference
    now = datetime.now(timezone.utc)
    wo.cmms_ref       = result["gist_id"]
    wo.cmms_synced_at = now
    db.commit()

    logger.info("CMMS sync: %s → %s", wo.order_number, result["gist_url"])
    return CMMSSyncResult(
        work_order_id=str(wo.id),
        order_number=wo.order_number,
        gist_id=result["gist_id"],
        gist_url=result["gist_url"],
        cmms_synced_at=now,
    )


@router.get("/sync/{work_order_id}", response_model=CMMSSyncStatus)
def get_cmms_sync_status(work_order_id: str, db: Session = Depends(get_db)):
    """Return the CMMS sync status for a work order."""
    wo = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    if not wo:
        raise HTTPException(status_code=404, detail=f"Work order '{work_order_id}' not found")

    gist_url = (
        f"https://gist.github.com/{wo.cmms_ref}" if wo.cmms_ref else None
    )
    return CMMSSyncStatus(
        work_order_id=str(wo.id),
        order_number=wo.order_number,
        cmms_ref=wo.cmms_ref,
        cmms_gist_url=gist_url,
        cmms_synced_at=wo.cmms_synced_at,
        synced=(wo.cmms_ref is not None),
    )


@router.post("/ingest", response_model=WorkOrderResponse, status_code=201)
def ingest_cmms_work_order(body: CMMSIngestRequest, db: Session = Depends(get_db)):
    """Import a CMMS work order into the MES database.

    Resolves product by SKU and line by name.
    If order_number already exists, returns the existing WO (idempotent).
    Sets cmms_ref to mark this WO as CMMS-originated.
    """
    # Idempotency — return existing WO if order_number already in DB
    existing = db.query(WorkOrder).filter(
        WorkOrder.order_number == body.order_number
    ).first()
    if existing:
        logger.info("CMMS ingest: %s already exists, returning existing", body.order_number)
        return _to_response(existing)

    # Resolve line by name
    line = db.query(Line).filter(Line.name == body.line_name).first()
    if not line:
        raise HTTPException(
            status_code=404,
            detail=f"Line '{body.line_name}' not found. Available: Conveyor-1, Sorting-1",
        )

    # Resolve product by SKU
    product = db.query(Product).filter(Product.sku == body.product_sku).first()
    if not product:
        raise HTTPException(
            status_code=404,
            detail=f"Product SKU '{body.product_sku}' not found. Create it first via POST /api/mes/products",
        )

    wo = WorkOrder(
        order_number=body.order_number,
        product_id=product.id,
        line_id=line.id,
        target_qty=body.target_qty,
        notes=body.notes,
        status=WorkOrderStatus.PENDING,
        cmms_ref=body.cmms_ref,
        cmms_synced_at=datetime.now(timezone.utc) if body.cmms_ref else None,
    )
    db.add(wo)
    db.commit()
    db.refresh(wo)
    logger.info(
        "CMMS ingest: created WO %s (line=%s, sku=%s, cmms_ref=%s)",
        wo.order_number, line.name, product.sku, wo.cmms_ref,
    )
    return _to_response(wo)
