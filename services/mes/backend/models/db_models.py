"""SQLAlchemy ORM models — MES Core schema.

7 tables:
  lines             — configured production lines
  products          — SKUs with ideal cycle times for OEE
  work_orders       — production jobs (create → active → complete)
  schedules         — shift-based production schedule
  downtime_reasons  — lookup table of reason codes (seeded in migration)
  machine_states    — time-series of state transitions per line
  oee_snapshots     — computed OEE snapshots (60s tick per active line)
"""

import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Column,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Index,
    Integer,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from backend.database import Base


# ── Enum types ────────────────────────────────────────────────────────────────

class WorkOrderStatus(str, enum.Enum):
    PENDING   = "PENDING"
    ACTIVE    = "ACTIVE"
    PAUSED    = "PAUSED"
    COMPLETE  = "COMPLETE"
    CANCELLED = "CANCELLED"


class MachineStateEnum(str, enum.Enum):
    RUNNING    = "RUNNING"
    DOWN       = "DOWN"
    CHANGEOVER = "CHANGEOVER"
    IDLE       = "IDLE"
    OFFLINE    = "OFFLINE"


class DowntimeCategory(str, enum.Enum):
    PLANNED   = "PLANNED"
    UNPLANNED = "UNPLANNED"
    EXTERNAL  = "EXTERNAL"


class EnteredBy(str, enum.Enum):
    PLC      = "PLC"
    OPERATOR = "OPERATOR"
    MIRA_AI  = "MIRA_AI"


class ShiftEnum(str, enum.Enum):
    DAY     = "DAY"
    NIGHT   = "NIGHT"
    WEEKEND = "WEEKEND"


# ── Tables ────────────────────────────────────────────────────────────────────

class Line(Base):
    """A physical production line (conveyor, cell, etc.)."""
    __tablename__ = "lines"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name        = Column(Text, unique=True, nullable=False)
    isa95_path  = Column(Text, nullable=False)    # e.g. "lakewales/floor/conveyor-1"
    plc_host    = Column(Text, nullable=False)    # e.g. "192.168.1.100"
    plc_port    = Column(Integer, default=502)
    description = Column(Text)
    created_at  = Column(DateTime(timezone=True), server_default=text("NOW()"))

    work_orders    = relationship("WorkOrder", back_populates="line")
    machine_states = relationship("MachineState", back_populates="line")
    oee_snapshots  = relationship("OEESnapshot", back_populates="line")
    schedules      = relationship("Schedule", back_populates="line")


class Product(Base):
    """A manufacturable SKU with ideal cycle time for Performance OEE."""
    __tablename__ = "products"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sku             = Column(Text, unique=True, nullable=False)
    name            = Column(Text, nullable=False)
    ideal_cycle_sec = Column(Float, nullable=False)  # seconds per part at 100% performance
    description     = Column(Text)
    created_at      = Column(DateTime(timezone=True), server_default=text("NOW()"))

    work_orders = relationship("WorkOrder", back_populates="product")


class WorkOrder(Base):
    """A discrete production job: product + line + target quantity."""
    __tablename__ = "work_orders"

    id               = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_number     = Column(Text, unique=True, nullable=False)
    product_id       = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    line_id          = Column(UUID(as_uuid=True), ForeignKey("lines.id"), nullable=False)
    target_qty       = Column(Integer, nullable=False)
    good_qty         = Column(Integer, default=0, nullable=False)
    status           = Column(
        SAEnum(WorkOrderStatus, name="work_order_status"),
        default=WorkOrderStatus.PENDING,
        nullable=False,
    )
    scheduled_start  = Column(DateTime(timezone=True))
    actual_start     = Column(DateTime(timezone=True))
    actual_end       = Column(DateTime(timezone=True))
    notes            = Column(Text)
    created_at       = Column(DateTime(timezone=True), server_default=text("NOW()"))
    updated_at       = Column(DateTime(timezone=True), server_default=text("NOW()"), onupdate=datetime.utcnow)

    product       = relationship("Product", back_populates="work_orders")
    line          = relationship("Line", back_populates="work_orders")
    oee_snapshots = relationship("OEESnapshot", back_populates="work_order")

    __table_args__ = (
        Index("idx_work_orders_line_id", "line_id"),
        Index("idx_work_orders_status", "status"),
    )


class Schedule(Base):
    """Maps a work order to a shift on a specific line."""
    __tablename__ = "schedules"

    id             = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    work_order_id  = Column(UUID(as_uuid=True), ForeignKey("work_orders.id"), nullable=False)
    line_id        = Column(UUID(as_uuid=True), ForeignKey("lines.id"), nullable=False)
    shift          = Column(SAEnum(ShiftEnum, name="shift_enum"), nullable=False)
    planned_start  = Column(DateTime(timezone=True), nullable=False)
    planned_end    = Column(DateTime(timezone=True), nullable=False)
    planned_qty    = Column(Integer, nullable=False)
    created_at     = Column(DateTime(timezone=True), server_default=text("NOW()"))

    work_order = relationship("WorkOrder")
    line       = relationship("Line", back_populates="schedules")


class DowntimeReason(Base):
    """Lookup table of reason codes for machine downtime.

    Seeded in the initial migration with 14 standard codes.
    Extensible via INSERT — do not remove existing codes.
    """
    __tablename__ = "downtime_reasons"

    code        = Column(Text, primary_key=True)   # e.g. "MAINT_BREAKDOWN"
    description = Column(Text, nullable=False)
    category    = Column(SAEnum(DowntimeCategory, name="downtime_category"), nullable=False)
    created_at  = Column(DateTime(timezone=True), server_default=text("NOW()"))

    machine_states = relationship("MachineState", back_populates="reason")


class MachineState(Base):
    """Time-series of machine state transitions per line.

    State machine:
      IDLE → RUNNING (motor_running coil = 1)
      RUNNING → DOWN (fault_alarm coil = 1)
      ANY → OFFLINE (PLC unreachable > 10s)
      DOWN / OFFLINE → IDLE (fault cleared, no run command)
    """
    __tablename__ = "machine_states"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    line_id     = Column(UUID(as_uuid=True), ForeignKey("lines.id"), nullable=False)
    state       = Column(SAEnum(MachineStateEnum, name="machine_state_enum"), nullable=False)
    started_at  = Column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))
    ended_at    = Column(DateTime(timezone=True))
    reason_code = Column(Text, ForeignKey("downtime_reasons.code"))  # NULL when RUNNING/IDLE
    entered_by  = Column(SAEnum(EnteredBy, name="entered_by_enum"), default=EnteredBy.PLC)
    notes       = Column(Text)

    line   = relationship("Line", back_populates="machine_states")
    reason = relationship("DowntimeReason", back_populates="machine_states")

    __table_args__ = (
        Index("idx_machine_states_line_id", "line_id"),
        Index("idx_machine_states_started_at", "started_at"),
    )


class OEESnapshot(Base):
    """OEE computed snapshot — written every 60s per active line.

    OEE = Availability × Performance × Quality
      Availability = run_time_sec / planned_time_sec
      Performance  = (ideal_cycle_sec × total_count) / run_time_sec
      Quality      = good_count / total_count
      TEEP         = oee × utilization (scheduled / max possible time)

    PLC register sources (main CLAUDE.md):
      motor_running  → Coil 0  (state = RUNNING)
      fault_alarm    → Coil 2  (state = DOWN)
      motor_speed    → HR100   (0-100, raw)
      conveyor_speed → HR104   (0-100, raw)
      error_code     → HR105   (0=none .. 7=estop)
    """
    __tablename__ = "oee_snapshots"

    id               = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    line_id          = Column(UUID(as_uuid=True), ForeignKey("lines.id"), nullable=False)
    work_order_id    = Column(UUID(as_uuid=True), ForeignKey("work_orders.id"))  # NULL if no active WO
    ts               = Column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))
    run_time_sec     = Column(Integer, nullable=False, default=0)
    planned_time_sec = Column(Integer, nullable=False, default=0)
    total_count      = Column(Integer, nullable=False, default=0)
    good_count       = Column(Integer, nullable=False, default=0)
    ideal_cycle_sec  = Column(Float, nullable=False, default=1.0)
    availability     = Column(Float, nullable=False, default=0.0)  # 0.0 – 1.0
    performance      = Column(Float, nullable=False, default=0.0)  # 0.0 – 1.0
    quality          = Column(Float, nullable=False, default=0.0)  # 0.0 – 1.0
    oee              = Column(Float, nullable=False, default=0.0)  # 0.0 – 1.0
    teep             = Column(Float)                               # nullable until schedule exists

    line       = relationship("Line", back_populates="oee_snapshots")
    work_order = relationship("WorkOrder", back_populates="oee_snapshots")

    __table_args__ = (
        Index("idx_oee_snapshots_line_id", "line_id"),
        Index("idx_oee_snapshots_ts", "ts"),
    )
