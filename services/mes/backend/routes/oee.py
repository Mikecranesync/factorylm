"""OEE routes — snapshots, history, fleet summary, KPIs.

Week 3 endpoints:
  GET /api/mes/lines/{id}/oee
  GET /api/mes/lines/{id}/oee/history
  GET /api/mes/oee/summary
  GET /api/mes/kpis
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.db_models import Line, MachineStateEnum, OEESnapshot
from backend.services import oee_calculator, state_poller

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mes", tags=["oee"])


# ── Response models ───────────────────────────────────────────────────────────

class OEESnapshotResponse(BaseModel):
    line_id:          str
    line_name:        str
    ts:               datetime
    availability:     float
    performance:      float
    quality:          float
    oee:              float
    teep:             Optional[float]
    run_time_sec:     int
    planned_time_sec: int
    total_count:      int
    good_count:       int
    ideal_cycle_sec:  float
    low_oee_ticks:    int   # consecutive ticks below 60% (alert indicator)


class OEEHistoryItem(BaseModel):
    ts:           datetime
    availability: float
    performance:  float
    quality:      float
    oee:          float
    total_count:  int
    run_time_sec: int


class OEESummaryItem(BaseModel):
    line_id:      str
    line_name:    str
    oee:          float
    availability: float
    performance:  float
    quality:      float
    teep:         Optional[float]
    run_state:    str
    ts:           Optional[datetime]
    alert:        bool  # True if low_oee_ticks >= 30


class KPIResponse(BaseModel):
    fleet_oee:              float   # average OEE across all lines (latest tick)
    downtime_minutes_today: int     # total DOWN + OFFLINE minutes today, all lines
    lines_in_alert:         int     # lines with OEE < 60% for 30+ min
    snapshot_ts:            datetime


# ── Helpers ───────────────────────────────────────────────────────────────────

def _latest_snapshot(db: Session, line_id: str) -> Optional[OEESnapshot]:
    return (
        db.query(OEESnapshot)
        .filter(OEESnapshot.line_id == line_id)
        .order_by(OEESnapshot.ts.desc())
        .first()
    )


def _downtime_minutes_today(db: Session, line_id: str) -> int:
    """Sum minutes in DOWN or OFFLINE state since midnight UTC today."""
    midnight = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    row = db.execute(
        text("""
            SELECT COALESCE(SUM(
                EXTRACT(EPOCH FROM (
                    COALESCE(ended_at, NOW()) - GREATEST(started_at, :midnight)
                ))
            ), 0) / 60
            FROM machine_states
            WHERE line_id = :lid
              AND state IN ('DOWN', 'OFFLINE')
              AND COALESCE(ended_at, NOW()) >= :midnight
        """),
        {"lid": line_id, "midnight": midnight},
    ).scalar()
    return int(row or 0)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/lines/{line_id}/oee", response_model=OEESnapshotResponse)
def get_line_oee(line_id: str, db: Session = Depends(get_db)):
    """Latest OEE snapshot for one line."""
    line = db.query(Line).filter(Line.id == line_id).first()
    if not line:
        raise HTTPException(status_code=404, detail=f"Line {line_id} not found")

    snap = _latest_snapshot(db, line_id)
    if not snap:
        raise HTTPException(
            status_code=404,
            detail="No OEE snapshots yet — calculator ticks every 60s",
        )

    return OEESnapshotResponse(
        line_id=line_id,
        line_name=line.name,
        ts=snap.ts,
        availability=snap.availability,
        performance=snap.performance,
        quality=snap.quality,
        oee=snap.oee,
        teep=snap.teep,
        run_time_sec=snap.run_time_sec,
        planned_time_sec=snap.planned_time_sec,
        total_count=snap.total_count,
        good_count=snap.good_count,
        ideal_cycle_sec=snap.ideal_cycle_sec,
        low_oee_ticks=oee_calculator.get_low_oee_ticks(line_id),
    )


@router.get("/lines/{line_id}/oee/history", response_model=list[OEEHistoryItem])
def get_line_oee_history(
    line_id: str,
    hours: int = Query(default=8, ge=1, le=72),
    db: Session = Depends(get_db),
):
    """OEE time-series for one line over the last N hours (default 8)."""
    line = db.query(Line).filter(Line.id == line_id).first()
    if not line:
        raise HTTPException(status_code=404, detail=f"Line {line_id} not found")

    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    snaps = (
        db.query(OEESnapshot)
        .filter(OEESnapshot.line_id == line_id, OEESnapshot.ts >= since)
        .order_by(OEESnapshot.ts.asc())
        .all()
    )
    return [
        OEEHistoryItem(
            ts=s.ts,
            availability=s.availability,
            performance=s.performance,
            quality=s.quality,
            oee=s.oee,
            total_count=s.total_count,
            run_time_sec=s.run_time_sec,
        )
        for s in snaps
    ]


@router.get("/oee/summary", response_model=list[OEESummaryItem])
def get_oee_summary(db: Session = Depends(get_db)):
    """Fleet OEE — latest snapshot for every configured line."""
    lines = db.query(Line).order_by(Line.name).all()
    result = []
    for line in lines:
        line_id = str(line.id)
        snap = _latest_snapshot(db, line_id)
        state = state_poller.get_cached_state(line_id)
        low_ticks = oee_calculator.get_low_oee_ticks(line_id)
        result.append(OEESummaryItem(
            line_id=line_id,
            line_name=line.name,
            oee=snap.oee if snap else 0.0,
            availability=snap.availability if snap else 0.0,
            performance=snap.performance if snap else 0.0,
            quality=snap.quality if snap else 0.0,
            teep=snap.teep if snap else None,
            run_state=state.value if state else MachineStateEnum.OFFLINE.value,
            ts=snap.ts if snap else None,
            alert=(low_ticks >= oee_calculator.OEE_ALERT_TICKS),
        ))
    return result


@router.get("/kpis", response_model=KPIResponse)
def get_kpis(db: Session = Depends(get_db)):
    """Aggregate KPIs: fleet OEE, total downtime minutes today, alert count."""
    lines = db.query(Line).all()
    oee_values = []
    total_downtime = 0
    alert_count = 0

    for line in lines:
        line_id = str(line.id)
        snap = _latest_snapshot(db, line_id)
        if snap:
            oee_values.append(snap.oee)
        total_downtime += _downtime_minutes_today(db, line_id)
        if oee_calculator.get_low_oee_ticks(line_id) >= oee_calculator.OEE_ALERT_TICKS:
            alert_count += 1

    fleet_oee = round(sum(oee_values) / len(oee_values), 4) if oee_values else 0.0

    return KPIResponse(
        fleet_oee=fleet_oee,
        downtime_minutes_today=total_downtime,
        lines_in_alert=alert_count,
        snapshot_ts=datetime.now(timezone.utc),
    )
