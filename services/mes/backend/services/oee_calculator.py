"""OEE Calculator — 60-second tick per active line.

Computes Availability, Performance, Quality, OEE, and TEEP from:
  - ItemCount delta (HR100) via plc-modbus HTTP
  - RUNNING-state duration from machine_states table
  - Active work order's ideal_cycle_sec (default 1.0 until Week 4)

Writes one oee_snapshots row per line per tick.
Raises an in-process alert when a line's OEE < 0.60 for 30+ consecutive
minutes (30 ticks at 60s each).

Formula:
  Availability = run_time_sec / planned_time_sec          (clamped 0-1)
  Performance  = (ideal_cycle_sec * total_count) / run_time_sec  (clamped 0-1)
  Quality      = good_count / total_count                 (clamped 0-1)
  OEE          = A * P * Q
  TEEP         = OEE  (utilisation = 1.0 until schedule wired in Week 4)
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database import SessionLocal
from backend.models.db_models import Line, MachineStateEnum, OEESnapshot
from backend.services import state_poller
from backend.services.plc_client import PLCOfflineError, fetch_io, item_count

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

TICK_SEC = 60               # OEE snapshot interval
OEE_ALERT_THRESHOLD = 0.60  # alert below this
OEE_ALERT_TICKS = 30        # consecutive ticks below threshold before alert (30 min)
DEFAULT_IDEAL_CYCLE_SEC = 1.0

# ── In-memory state ───────────────────────────────────────────────────────────

# {line_id: int}  — ItemCount at previous tick (cumulative register)
_last_count: dict = {}

# {line_id: int}  — consecutive ticks below OEE_ALERT_THRESHOLD
_low_oee_ticks: dict = {}

_stop_event: Optional[asyncio.Event] = None


# ── OEE math (pure functions) ─────────────────────────────────────────────────

def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def compute_oee(
    run_time_sec: int,
    planned_time_sec: int,
    total_count: int,
    good_count: int,
    ideal_cycle_sec: float,
) -> dict:
    """Return dict with availability, performance, quality, oee, teep.

    All outputs clamped to [0.0, 1.0].
    Division-by-zero safe — returns 0.0 on any degenerate input.
    """
    if planned_time_sec <= 0:
        return dict(availability=0.0, performance=0.0, quality=0.0, oee=0.0, teep=0.0)

    availability = _clamp(run_time_sec / planned_time_sec)

    if run_time_sec > 0 and total_count > 0:
        performance = _clamp((ideal_cycle_sec * total_count) / run_time_sec)
    else:
        performance = 0.0

    quality = _clamp(good_count / total_count) if total_count > 0 else 0.0

    oee = availability * performance * quality
    teep = oee  # utilisation = 1.0 until Week 4 adds schedule

    return dict(
        availability=round(availability, 4),
        performance=round(performance, 4),
        quality=round(quality, 4),
        oee=round(oee, 4),
        teep=round(teep, 4),
    )


# ── DB helpers ────────────────────────────────────────────────────────────────

def _run_time_in_window(db: Session, line_id: str, window_sec: int) -> int:
    """Sum seconds spent in RUNNING state in the last window_sec seconds."""
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=window_sec)
    rows = db.execute(
        text("""
            SELECT
                GREATEST(started_at, :cutoff) AS seg_start,
                COALESCE(ended_at, NOW())      AS seg_end
            FROM machine_states
            WHERE line_id  = :lid
              AND state     = 'RUNNING'
              AND COALESCE(ended_at, NOW()) >= :cutoff
        """),
        {"lid": line_id, "cutoff": cutoff},
    ).fetchall()
    total = 0
    for row in rows:
        seg_start, seg_end = row[0], row[1]
        if seg_end > seg_start:
            total += int((seg_end - seg_start).total_seconds())
    return min(total, window_sec)


def _active_ideal_cycle(db: Session, line_id: str) -> float:
    """Return ideal_cycle_sec from the active work order's product, or default."""
    row = db.execute(
        text("""
            SELECT p.ideal_cycle_sec
            FROM work_orders wo
            JOIN products p ON p.id = wo.product_id
            WHERE wo.line_id = :lid AND wo.status = 'ACTIVE'
            LIMIT 1
        """),
        {"lid": line_id},
    ).fetchone()
    return float(row[0]) if row else DEFAULT_IDEAL_CYCLE_SEC


def _active_work_order_id(db: Session, line_id: str) -> Optional[str]:
    row = db.execute(
        text("SELECT id FROM work_orders WHERE line_id=:lid AND status='ACTIVE' LIMIT 1"),
        {"lid": line_id},
    ).fetchone()
    return str(row[0]) if row else None


def _write_snapshot(db: Session, line_id: str, work_order_id: Optional[str],
                    run_time_sec: int, planned_time_sec: int,
                    total_count: int, good_count: int,
                    ideal_cycle_sec: float, metrics: dict) -> None:
    snap = OEESnapshot(
        line_id=line_id,
        work_order_id=work_order_id,
        ts=datetime.now(timezone.utc),
        run_time_sec=run_time_sec,
        planned_time_sec=planned_time_sec,
        total_count=total_count,
        good_count=good_count,
        ideal_cycle_sec=ideal_cycle_sec,
        availability=metrics["availability"],
        performance=metrics["performance"],
        quality=metrics["quality"],
        oee=metrics["oee"],
        teep=metrics["teep"],
    )
    db.add(snap)


# ── Alert logic ───────────────────────────────────────────────────────────────

def _check_alert(line_name: str, line_id: str, oee: float) -> None:
    if oee < OEE_ALERT_THRESHOLD:
        _low_oee_ticks[line_id] = _low_oee_ticks.get(line_id, 0) + 1
        if _low_oee_ticks[line_id] == OEE_ALERT_TICKS:
            logger.warning(
                "ALERT  Line %-12s  OEE %.1f%% below %.0f%% for %d consecutive minutes",
                line_name, oee * 100, OEE_ALERT_THRESHOLD * 100, OEE_ALERT_TICKS,
            )
    else:
        _low_oee_ticks[line_id] = 0


# ── Per-line tick ─────────────────────────────────────────────────────────────

async def _tick_line(line: Line) -> None:
    """Compute and persist one OEE snapshot for a single line."""
    line_id = str(line.id)

    # Skip if OFFLINE — no meaningful OEE
    current_state = state_poller.get_cached_state(line_id)
    is_offline = (current_state == MachineStateEnum.OFFLINE or current_state is None)
    planned_time_sec = 0 if is_offline else TICK_SEC

    # Fetch current item count (non-blocking)
    total_count = 0
    try:
        io_data = await fetch_io(settings.plc_modbus_url)
        current_count = item_count(io_data)
        prev = _last_count.get(line_id)
        if prev is None:
            # First tick — seed without counting; no items to credit yet
            _last_count[line_id] = current_count
            logger.debug("Line %s — seeding count at %d", line.name, current_count)
            return
        delta = max(0, current_count - prev)
        _last_count[line_id] = current_count
        total_count = delta
    except PLCOfflineError:
        # PLC unreachable — keep count at 0 for this tick
        pass

    good_count = total_count  # no reject tracking until Week 5

    # DB work in thread
    def _db_work():
        db = SessionLocal()
        try:
            run_time_sec = _run_time_in_window(db, line_id, TICK_SEC)
            ideal_cycle_sec = _active_ideal_cycle(db, line_id)
            wo_id = _active_work_order_id(db, line_id)

            metrics = compute_oee(
                run_time_sec=run_time_sec,
                planned_time_sec=planned_time_sec,
                total_count=total_count,
                good_count=good_count,
                ideal_cycle_sec=ideal_cycle_sec,
            )
            _write_snapshot(db, line_id, wo_id, run_time_sec, planned_time_sec,
                            total_count, good_count, ideal_cycle_sec, metrics)
            db.commit()
            return metrics, ideal_cycle_sec, run_time_sec
        except Exception:
            db.rollback()
            logger.exception("OEE snapshot write failed for line %s", line.name)
            return None, DEFAULT_IDEAL_CYCLE_SEC, 0
        finally:
            db.close()

    result = await asyncio.to_thread(_db_work)
    metrics, ideal_cycle_sec, run_time_sec = result
    if metrics:
        _check_alert(line.name, line_id, metrics["oee"])
        logger.info(
            "OEE  %-12s  A=%.2f  P=%.2f  Q=%.2f  OEE=%.2f  "
            "run=%ds  count=%d  cycle=%.1fs",
            line.name,
            metrics["availability"], metrics["performance"],
            metrics["quality"], metrics["oee"],
            run_time_sec, total_count, ideal_cycle_sec,
        )


# ── Tick loop ─────────────────────────────────────────────────────────────────

async def run(tick_sec: int = TICK_SEC) -> None:
    """Background OEE calculator — one tick per line every tick_sec seconds."""
    global _stop_event
    _stop_event = asyncio.Event()
    logger.info("OEE calculator starting (tick=%ds, threshold=%.0f%%)",
                tick_sec, OEE_ALERT_THRESHOLD * 100)

    tick = 0
    lines: list = []

    while not _stop_event.is_set():
        if tick % 60 == 0:
            db = SessionLocal()
            try:
                lines = db.query(Line).all()
            finally:
                db.close()

        if lines:
            await asyncio.gather(
                *[_tick_line(line) for line in lines],
                return_exceptions=True,
            )

        tick += 1
        try:
            await asyncio.wait_for(_stop_event.wait(), timeout=tick_sec)
        except asyncio.TimeoutError:
            pass


def stop() -> None:
    if _stop_event:
        _stop_event.set()


# ── Public read API (used by routes) ─────────────────────────────────────────

def get_low_oee_ticks(line_id: str) -> int:
    """How many consecutive ticks has this line been below threshold."""
    return _low_oee_ticks.get(line_id, 0)
