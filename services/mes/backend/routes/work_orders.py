"""Work Order routes — CRUD + status transitions.

Week 4 endpoints:
  POST  /api/mes/products                    — create a product (SKU + ideal cycle)
  GET   /api/mes/products                    — list all products
  POST  /api/mes/work-orders                 — create a work order
  GET   /api/mes/work-orders                 — list (filter ?line_id= ?status=)
  GET   /api/mes/work-orders/{id}            — detail
  PATCH /api/mes/work-orders/{id}/status     — PENDING→ACTIVE→COMPLETE / CANCELLED

Transition rules:
  PENDING  → ACTIVE     (start the job)
  ACTIVE   → COMPLETE   (job done)
  ACTIVE   → CANCELLED
  PENDING  → CANCELLED

Constraint: one line can only have ONE ACTIVE work order at a time (409 on violation).
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.db_models import Line, Product, WorkOrder, WorkOrderStatus
from backend.models.mes_models import WorkOrderCreate, WorkOrderResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mes", tags=["work-orders"])


# ── Valid status transitions ───────────────────────────────────────────────────

_ALLOWED_TRANSITIONS = {
    WorkOrderStatus.PENDING:  {WorkOrderStatus.ACTIVE, WorkOrderStatus.CANCELLED},
    WorkOrderStatus.ACTIVE:   {WorkOrderStatus.COMPLETE, WorkOrderStatus.CANCELLED},
    WorkOrderStatus.PAUSED:   {WorkOrderStatus.ACTIVE, WorkOrderStatus.CANCELLED},
    WorkOrderStatus.COMPLETE:  set(),
    WorkOrderStatus.CANCELLED: set(),
}


# ── Request / response models ──────────────────────────────────────────────────

class ProductCreate(BaseModel):
    sku:             str
    name:            str
    ideal_cycle_sec: float = Field(gt=0, description="Seconds per part at 100% performance")
    description:     Optional[str] = None


class ProductResponse(BaseModel):
    id:              str
    sku:             str
    name:            str
    ideal_cycle_sec: float
    description:     Optional[str] = None

    model_config = {"from_attributes": True}


class WorkOrderStatusUpdate(BaseModel):
    status: str  # validated against allowed transitions at runtime


# ── Product endpoints ──────────────────────────────────────────────────────────

@router.post("/products", response_model=ProductResponse, status_code=201)
def create_product(body: ProductCreate, db: Session = Depends(get_db)):
    """Create a new product SKU with an ideal cycle time."""
    existing = db.query(Product).filter(Product.sku == body.sku).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Product SKU '{body.sku}' already exists")

    product = Product(
        sku=body.sku,
        name=body.name,
        ideal_cycle_sec=body.ideal_cycle_sec,
        description=body.description,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    logger.info("Product created: %s (%.2fs/part)", product.sku, product.ideal_cycle_sec)
    return ProductResponse(
        id=str(product.id),
        sku=product.sku,
        name=product.name,
        ideal_cycle_sec=product.ideal_cycle_sec,
        description=product.description,
    )


@router.get("/products", response_model=list[ProductResponse])
def list_products(db: Session = Depends(get_db)):
    """List all products."""
    products = db.query(Product).order_by(Product.sku).all()
    return [
        ProductResponse(
            id=str(p.id),
            sku=p.sku,
            name=p.name,
            ideal_cycle_sec=p.ideal_cycle_sec,
            description=p.description,
        )
        for p in products
    ]


# ── Work order endpoints ───────────────────────────────────────────────────────

@router.post("/work-orders", response_model=WorkOrderResponse, status_code=201)
def create_work_order(body: WorkOrderCreate, db: Session = Depends(get_db)):
    """Create a new work order (status = PENDING)."""
    # Validate line exists
    line = db.query(Line).filter(Line.id == body.line_id).first()
    if not line:
        raise HTTPException(status_code=404, detail=f"Line '{body.line_id}' not found")

    # Validate product exists
    product = db.query(Product).filter(Product.id == body.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail=f"Product '{body.product_id}' not found")

    # Unique order number
    if db.query(WorkOrder).filter(WorkOrder.order_number == body.order_number).first():
        raise HTTPException(status_code=409, detail=f"Order number '{body.order_number}' already exists")

    wo = WorkOrder(
        order_number=body.order_number,
        product_id=body.product_id,
        line_id=body.line_id,
        target_qty=body.target_qty,
        scheduled_start=body.scheduled_start,
        notes=body.notes,
        status=WorkOrderStatus.PENDING,
    )
    db.add(wo)
    db.commit()
    db.refresh(wo)
    logger.info("Work order created: %s → line=%s qty=%d", wo.order_number, line.name, wo.target_qty)
    return _to_response(wo)


@router.get("/work-orders", response_model=list[WorkOrderResponse])
def list_work_orders(
    line_id: Optional[str] = Query(default=None),
    status:  Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    """List work orders, optionally filtered by line_id and/or status."""
    q = db.query(WorkOrder)
    if line_id:
        q = q.filter(WorkOrder.line_id == line_id)
    if status:
        try:
            s = WorkOrderStatus(status.upper())
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Unknown status '{status}'")
        q = q.filter(WorkOrder.status == s)
    return [_to_response(wo) for wo in q.order_by(WorkOrder.created_at.desc()).all()]


@router.get("/work-orders/{work_order_id}", response_model=WorkOrderResponse)
def get_work_order(work_order_id: str, db: Session = Depends(get_db)):
    """Get a single work order by ID."""
    wo = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    if not wo:
        raise HTTPException(status_code=404, detail=f"Work order '{work_order_id}' not found")
    return _to_response(wo)


@router.patch("/work-orders/{work_order_id}/status", response_model=WorkOrderResponse)
def update_work_order_status(
    work_order_id: str,
    body: WorkOrderStatusUpdate,
    db: Session = Depends(get_db),
):
    """Transition a work order's status.

    PENDING → ACTIVE → COMPLETE
    PENDING → CANCELLED
    ACTIVE  → CANCELLED
    """
    wo = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    if not wo:
        raise HTTPException(status_code=404, detail=f"Work order '{work_order_id}' not found")

    # Parse and validate new status
    try:
        new_status = WorkOrderStatus(body.status.upper())
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Unknown status '{body.status}'")

    allowed = _ALLOWED_TRANSITIONS.get(wo.status, set())
    if new_status not in allowed:
        raise HTTPException(
            status_code=422,
            detail=f"Cannot transition from {wo.status.value} to {new_status.value}. "
                   f"Allowed: {[s.value for s in allowed] or 'none'}",
        )

    # Enforce one-ACTIVE-per-line
    if new_status == WorkOrderStatus.ACTIVE:
        conflict = (
            db.query(WorkOrder)
            .filter(
                WorkOrder.line_id == wo.line_id,
                WorkOrder.status == WorkOrderStatus.ACTIVE,
                WorkOrder.id != wo.id,
            )
            .first()
        )
        if conflict:
            raise HTTPException(
                status_code=409,
                detail=f"Line already has an active work order: {conflict.order_number}",
            )

    # Apply transition
    now = datetime.now(timezone.utc)
    if new_status == WorkOrderStatus.ACTIVE and wo.actual_start is None:
        wo.actual_start = now
    elif new_status in (WorkOrderStatus.COMPLETE, WorkOrderStatus.CANCELLED):
        wo.actual_end = now

    wo.status = new_status
    db.commit()
    db.refresh(wo)
    logger.info("Work order %s → %s", wo.order_number, new_status.value)
    return _to_response(wo)


# ── Helper ────────────────────────────────────────────────────────────────────

def _to_response(wo: WorkOrder) -> WorkOrderResponse:
    return WorkOrderResponse(
        id=str(wo.id),
        order_number=wo.order_number,
        product_id=str(wo.product_id),
        line_id=str(wo.line_id),
        target_qty=wo.target_qty,
        good_qty=wo.good_qty,
        status=wo.status.value,
        scheduled_start=wo.scheduled_start,
        actual_start=wo.actual_start,
        actual_end=wo.actual_end,
        notes=wo.notes,
        created_at=wo.created_at,
    )
