"""Downtime tracking routes — reason lookup, history, manual entry.

Week 5 endpoints:
  GET  /api/mes/downtime-reasons             — list all 14 reason codes
  GET  /api/mes/lines/{id}/downtime          — downtime events for one line
  POST /api/mes/lines/{id}/downtime          — attach reason to open DOWN event

POST accepts two modes:
  Direct:  { "reason_code": "JAM",         "entered_by": "OPERATOR" }
  NLP:     { "description": "line jammed", "entered_by": "MIRA_AI"  }

If description is given the NLP classifier maps it to a reason_code.
If the classifier returns UNKNOWN a confidence="low" warning is included.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.db_models import (
    DowntimeReason,
    EnteredBy,
    Line,
    MachineState,
    MachineStateEnum,
)
from backend.services.downtime_classifier import classify_reason

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mes", tags=["downtime"])


# ── Response models ───────────────────────────────────────────────────────────

class DowntimeReasonResponse(BaseModel):
    code:        str
    description: str
    category:    str  # PLANNED / UNPLANNED / EXTERNAL


class DowntimeEventResponse(BaseModel):
    id:           str
    line_id:      str
    state:        str
    reason_code:  Optional[str]
    reason_desc:  Optional[str]   # joined from downtime_reasons
    category:     Optional[str]   # PLANNED / UNPLANNED / EXTERNAL
    entered_by:   str
    notes:        Optional[str]
    started_at:   datetime
    ended_at:     Optional[datetime]
    duration_min: Optional[int]   # None if event is still open


class DowntimeEntryRequest(BaseModel):
    reason_code: Optional[str] = None   # direct code entry
    description: Optional[str] = None  # free-text → NLP classifier
    entered_by:  str = "OPERATOR"       # OPERATOR | MIRA_AI
    notes:       Optional[str] = None


class DowntimeEntryResponse(BaseModel):
    event:      DowntimeEventResponse
    classified: Optional[bool] = None   # True if NLP was used
    confidence: Optional[str]  = None   # "high" | "low" (NLP only)


# ── Helpers ───────────────────────────────────────────────────────────────────

_DOWN_STATES = (MachineStateEnum.DOWN.value, MachineStateEnum.CHANGEOVER.value)


def _to_event(row: MachineState, reason: Optional[DowntimeReason]) -> DowntimeEventResponse:
    now = datetime.now(timezone.utc)
    ended = row.ended_at
    duration = None
    if row.started_at:
        end_ts = ended if ended else now
        # Ensure both are timezone-aware before subtracting
        start_ts = row.started_at
        if start_ts.tzinfo is None:
            start_ts = start_ts.replace(tzinfo=timezone.utc)
        if end_ts.tzinfo is None:
            end_ts = end_ts.replace(tzinfo=timezone.utc)
        duration = max(0, int((end_ts - start_ts).total_seconds() / 60))

    return DowntimeEventResponse(
        id=str(row.id),
        line_id=str(row.line_id),
        state=row.state.value,
        reason_code=row.reason_code,
        reason_desc=reason.description if reason else None,
        category=reason.category.value if reason else None,
        entered_by=row.entered_by.value if row.entered_by else EnteredBy.PLC.value,
        notes=row.notes,
        started_at=row.started_at,
        ended_at=row.ended_at,
        duration_min=duration,
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/downtime-reasons", response_model=list[DowntimeReasonResponse])
def list_downtime_reasons(db: Session = Depends(get_db)):
    """All configured downtime reason codes (seeded 14 standard codes)."""
    reasons = db.query(DowntimeReason).order_by(DowntimeReason.category, DowntimeReason.code).all()
    return [
        DowntimeReasonResponse(
            code=r.code,
            description=r.description,
            category=r.category.value,
        )
        for r in reasons
    ]


@router.get("/lines/{line_id}/downtime", response_model=list[DowntimeEventResponse])
def get_line_downtime(
    line_id: str,
    hours: int = Query(default=8, ge=1, le=72),
    db: Session = Depends(get_db),
):
    """Downtime events (DOWN + CHANGEOVER) for a line over the last N hours."""
    line = db.query(Line).filter(Line.id == line_id).first()
    if not line:
        raise HTTPException(status_code=404, detail=f"Line {line_id} not found")

    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    rows = (
        db.query(MachineState)
        .filter(
            MachineState.line_id == line_id,
            MachineState.state.in_([MachineStateEnum.DOWN, MachineStateEnum.CHANGEOVER]),
            MachineState.started_at >= since,
        )
        .order_by(MachineState.started_at.desc())
        .all()
    )

    result = []
    for row in rows:
        reason = (
            db.query(DowntimeReason).filter(DowntimeReason.code == row.reason_code).first()
            if row.reason_code else None
        )
        result.append(_to_event(row, reason))
    return result


@router.post("/lines/{line_id}/downtime", response_model=DowntimeEntryResponse)
def enter_downtime_reason(
    line_id: str,
    body: DowntimeEntryRequest,
    db: Session = Depends(get_db),
):
    """Attach a downtime reason to the current open DOWN or CHANGEOVER event.

    Accepts either a direct reason_code or a free-text description (NLP classified).
    Returns 409 if the line has no open downtime event right now.
    """
    line = db.query(Line).filter(Line.id == line_id).first()
    if not line:
        raise HTTPException(status_code=404, detail=f"Line {line_id} not found")

    # Validate entered_by
    try:
        entered_by = EnteredBy(body.entered_by.upper())
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Unknown entered_by '{body.entered_by}'")

    # Find the most recent open DOWN/CHANGEOVER event
    open_event = (
        db.query(MachineState)
        .filter(
            MachineState.line_id == line_id,
            MachineState.state.in_([MachineStateEnum.DOWN, MachineStateEnum.CHANGEOVER]),
            MachineState.ended_at.is_(None),
        )
        .order_by(MachineState.started_at.desc())
        .first()
    )
    if not open_event:
        raise HTTPException(
            status_code=409,
            detail=f"Line {line.name} has no open DOWN or CHANGEOVER event. "
                   "Start a downtime event first (state must be DOWN or CHANGEOVER).",
        )

    # Resolve reason_code — direct or NLP
    classified = False
    confidence = None

    if body.reason_code:
        reason_code = body.reason_code.upper()
        # Validate code exists
        if not db.query(DowntimeReason).filter(DowntimeReason.code == reason_code).first():
            raise HTTPException(status_code=422, detail=f"Unknown reason code '{reason_code}'")
    elif body.description:
        reason_code, confidence = classify_reason(body.description)
        classified = True
        logger.info(
            "NLP classified '%s' → %s (confidence=%s) for line %s",
            body.description, reason_code, confidence, line.name,
        )
    else:
        raise HTTPException(
            status_code=422,
            detail="Provide either reason_code or description.",
        )

    # Update the open event
    open_event.reason_code = reason_code
    open_event.entered_by  = entered_by
    open_event.notes       = body.notes
    db.commit()
    db.refresh(open_event)

    reason_obj = db.query(DowntimeReason).filter(DowntimeReason.code == reason_code).first()
    logger.info(
        "Downtime reason set: line=%s  event=%s  code=%s  by=%s",
        line.name, open_event.id, reason_code, entered_by.value,
    )

    return DowntimeEntryResponse(
        event=_to_event(open_event, reason_obj),
        classified=classified if classified else None,
        confidence=confidence,
    )
