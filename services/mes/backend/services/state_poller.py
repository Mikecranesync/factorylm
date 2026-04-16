"""Background asyncio task that polls plc-modbus and writes state transitions.

One poller instance manages all configured lines.  It polls every
`poll_interval_sec` seconds (default 5) and writes to `machine_states`
only when the state changes for a line.

State cache:
    In-memory dict {line_id (str) -> MachineStateEnum}.
    Avoids a DB read on every tick — only transitions hit the DB.

Transition write:
    1. Find the open machine_state row for this line (ended_at IS NULL).
    2. Set ended_at = NOW() on that row.
    3. INSERT new row with new state + reason_code.

On startup:
    Seed the cache from the most recent open machine_state row per line.
    If none exists, insert an initial OFFLINE row.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database import SessionLocal
from backend.models.db_models import EnteredBy, Line, MachineState, MachineStateEnum
from backend.services.plc_client import PLCOfflineError, fetch_io
from backend.services.state_machine import detect_state, is_transition

logger = logging.getLogger(__name__)

# In-memory cache: line_id (str) -> current MachineStateEnum
_state_cache: dict = {}

# Set to True to stop the polling loop cleanly
_stop_event: Optional[asyncio.Event] = None


# ── DB helpers ────────────────────────────────────────────────────────────────

def _load_lines(db: Session) -> list:
    """Return all Line rows from DB."""
    return db.query(Line).all()


def _close_open_state(db: Session, line_id: str) -> None:
    """Set ended_at on the currently open machine_state row for this line."""
    db.execute(
        text(
            "UPDATE machine_states SET ended_at = :now "
            "WHERE line_id = :lid AND ended_at IS NULL"
        ),
        {"now": datetime.now(timezone.utc), "lid": line_id},
    )


def _insert_state(
    db: Session,
    line_id: str,
    state: MachineStateEnum,
    reason_code: Optional[str],
) -> None:
    """Insert a new open machine_state row."""
    row = MachineState(
        line_id=line_id,
        state=state,
        started_at=datetime.now(timezone.utc),
        reason_code=reason_code,
        entered_by=EnteredBy.PLC,
    )
    db.add(row)


def _apply_transition(
    line_id: str,
    new_state: MachineStateEnum,
    reason_code: Optional[str],
) -> None:
    """Write a state transition to the DB atomically."""
    db = SessionLocal()
    try:
        _close_open_state(db, line_id)
        _insert_state(db, line_id, new_state, reason_code)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Failed to write state transition for line %s", line_id)
    finally:
        db.close()


def _seed_cache_from_db() -> None:
    """On startup, load the latest open state per line into the cache."""
    db = SessionLocal()
    try:
        rows = db.execute(
            text(
                "SELECT DISTINCT ON (line_id) line_id, state "
                "FROM machine_states "
                "WHERE ended_at IS NULL "
                "ORDER BY line_id, started_at DESC"
            )
        ).fetchall()
        for row in rows:
            try:
                _state_cache[str(row[0])] = MachineStateEnum(row[1])
            except ValueError:
                pass
    finally:
        db.close()


# ── Core poll logic ───────────────────────────────────────────────────────────

async def _poll_line(line: Line) -> None:
    """Poll plc-modbus for one line and write a transition if state changed."""
    line_id = str(line.id)
    try:
        io_data = await fetch_io(settings.plc_modbus_url)
        new_state, reason_code = detect_state(io_data)
    except PLCOfflineError as exc:
        logger.warning("Line %s — PLC offline: %s", line.name, exc)
        new_state = MachineStateEnum.OFFLINE
        reason_code = "COMMS_FAIL"

    current = _state_cache.get(line_id)

    if is_transition(current, new_state):
        logger.info(
            "Line %-12s  %s → %s  (reason: %s)",
            line.name,
            current.value if current else "BOOT",
            new_state.value,
            reason_code or "—",
        )
        _state_cache[line_id] = new_state
        # DB write runs in a thread to avoid blocking the event loop
        await asyncio.to_thread(_apply_transition, line_id, new_state, reason_code)


async def _poll_all_lines(lines: list) -> None:
    """Poll all lines concurrently."""
    await asyncio.gather(*[_poll_line(line) for line in lines], return_exceptions=True)


# ── Poller lifecycle ──────────────────────────────────────────────────────────

async def run(poll_interval_sec: int = 5) -> None:
    """Main polling loop — runs until stop() is called.

    Loads lines from DB on first tick (and refreshes every 60 ticks
    to pick up lines added without a restart).
    """
    global _stop_event
    _stop_event = asyncio.Event()

    logger.info("State poller starting (interval=%ds)", poll_interval_sec)
    _seed_cache_from_db()

    tick = 0
    lines: list = []

    while not _stop_event.is_set():
        if tick % 60 == 0:  # reload line config every 5 min
            db = SessionLocal()
            try:
                lines = _load_lines(db)
                logger.info("Poller watching %d line(s): %s",
                            len(lines), [l.name for l in lines])
            finally:
                db.close()

        if lines:
            await _poll_all_lines(lines)

        tick += 1
        try:
            await asyncio.wait_for(_stop_event.wait(), timeout=poll_interval_sec)
        except asyncio.TimeoutError:
            pass  # normal — keep polling


def stop() -> None:
    """Signal the polling loop to exit cleanly."""
    if _stop_event:
        _stop_event.set()


# ── Public cache accessor ─────────────────────────────────────────────────────

def get_cached_state(line_id: str) -> Optional[MachineStateEnum]:
    """Return the last known state for a line (no DB hit)."""
    return _state_cache.get(line_id)
