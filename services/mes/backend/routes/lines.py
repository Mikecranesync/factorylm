"""Lines routes — GET /api/mes/lines and GET /api/mes/lines/{id}/state.

Week 2 endpoints only.  Work order and OEE endpoints added in later weeks.
"""

import logging
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.db_models import Line, MachineState, MachineStateEnum
from backend.models.mes_models import LineResponse
from backend.services import state_poller

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mes", tags=["mes"])


# ── Response models ───────────────────────────────────────────────────────────

class LineStateResponse(BaseModel):
    line_id:     str
    line_name:   str
    state:       str
    reason_code: Optional[str] = None
    since:       Optional[datetime] = None   # when this state started
    source:      str                          # "cache" | "db" | "unknown"


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/lines", response_model=list[LineResponse])
def list_lines(db: Session = Depends(get_db)):
    """Return all configured production lines."""
    lines = db.query(Line).order_by(Line.name).all()
    return [
        LineResponse(
            id=str(line.id),
            name=line.name,
            isa95_path=line.isa95_path,
            plc_host=line.plc_host,
            plc_port=line.plc_port,
            description=line.description,
        )
        for line in lines
    ]


@router.get("/lines/{line_id}/state", response_model=LineStateResponse)
def get_line_state(line_id: str, db: Session = Depends(get_db)):
    """Return the current machine state for a line.

    Checks the in-memory cache first (no DB hit on the hot path).
    Falls back to the most recent open DB row if the cache is cold
    (e.g. service just restarted but poller hasn't ticked yet).
    """
    line = db.query(Line).filter(Line.id == line_id).first()
    if not line:
        raise HTTPException(status_code=404, detail=f"Line {line_id} not found")

    # Try in-memory cache first
    cached = state_poller.get_cached_state(line_id)
    if cached is not None:
        # Get the `since` time from the latest open DB row (non-blocking, fast)
        open_row = (
            db.query(MachineState)
            .filter(MachineState.line_id == line_id, MachineState.ended_at.is_(None))
            .order_by(MachineState.started_at.desc())
            .first()
        )
        return LineStateResponse(
            line_id=line_id,
            line_name=line.name,
            state=cached.value,
            reason_code=open_row.reason_code if open_row else None,
            since=open_row.started_at if open_row else None,
            source="cache",
        )

    # Cache cold — fall back to DB
    open_row = (
        db.query(MachineState)
        .filter(MachineState.line_id == line_id, MachineState.ended_at.is_(None))
        .order_by(MachineState.started_at.desc())
        .first()
    )
    if open_row:
        return LineStateResponse(
            line_id=line_id,
            line_name=line.name,
            state=open_row.state.value,
            reason_code=open_row.reason_code,
            since=open_row.started_at,
            source="db",
        )

    return LineStateResponse(
        line_id=line_id,
        line_name=line.name,
        state=MachineStateEnum.OFFLINE.value,
        source="unknown",
    )
