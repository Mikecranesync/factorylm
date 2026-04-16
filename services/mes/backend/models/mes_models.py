"""Pydantic UDTs — Walker Reynolds' Week 4 concepts as Pydantic models.

These are the runtime data shapes published to the Unified Namespace (UNS)
via MQTT and returned by the MES REST API. They map to ORM rows in db_models.py
but are decoupled from SQLAlchemy so they can be used in non-DB contexts.

Reference: docs/PRD-MES-CORE.md — Section 5 (UDT Definitions)
"""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


# ── Walker's three UDTs ───────────────────────────────────────────────────────

class LineDataType(BaseModel):
    """Complete live snapshot for a single production line.

    Published to UNS topic: {isa95_path}/production/line_data
    Updated every 60s by the OEE calculator (Week 3).
    """
    line_id:              str
    isa95_path:           str
    run_state:            Literal["RUNNING", "DOWN", "CHANGEOVER", "IDLE", "OFFLINE"]
    oee:                  float = Field(ge=0.0, le=1.0)
    availability:         float = Field(ge=0.0, le=1.0)
    performance:          float = Field(ge=0.0, le=1.0)
    quality:              float = Field(ge=0.0, le=1.0)
    good_count:           int   = Field(ge=0)
    total_count:          int   = Field(ge=0)
    active_work_order_id: Optional[str] = None
    ts:                   datetime


class CountDispatch(BaseModel):
    """Part count increment event — published on every detected count.

    Published to UNS topic: {isa95_path}/production/count_dispatch
    Source: HR100 (ItemCount) delta since last poll.
    """
    line_id:    str
    count_type: Literal["GOOD", "REJECT", "TOTAL"]
    delta:      int = Field(ge=0, description="Parts counted since last dispatch")
    ts:         datetime


class OEEDataType(BaseModel):
    """OEE computation result for a single interval.

    Published to UNS topic: {isa95_path}/production/oee
    Written to oee_snapshots table every 60s.
    """
    line_id:          str
    interval_sec:     int   = Field(gt=0, description="Length of the measurement interval")
    availability:     float = Field(ge=0.0, le=1.0)
    performance:      float = Field(ge=0.0, le=1.0)
    quality:          float = Field(ge=0.0, le=1.0)
    oee:              float = Field(ge=0.0, le=1.0)
    teep:             Optional[float] = Field(default=None, ge=0.0, le=1.0)
    ts:               datetime


# ── REST API request / response models ───────────────────────────────────────

class LineResponse(BaseModel):
    id:          str
    name:        str
    isa95_path:  str
    plc_host:    str
    plc_port:    int
    description: Optional[str] = None

    model_config = {"from_attributes": True}


class WorkOrderCreate(BaseModel):
    order_number:    str
    product_id:      str
    line_id:         str
    target_qty:      int = Field(gt=0)
    scheduled_start: Optional[datetime] = None
    notes:           Optional[str] = None


class WorkOrderResponse(BaseModel):
    id:              str
    order_number:    str
    product_id:      str
    line_id:         str
    target_qty:      int
    good_qty:        int
    status:          str
    scheduled_start: Optional[datetime] = None
    actual_start:    Optional[datetime] = None
    actual_end:      Optional[datetime] = None
    notes:           Optional[str] = None
    created_at:      datetime

    model_config = {"from_attributes": True}


class WorkOrderStatusUpdate(BaseModel):
    status: Literal["PENDING", "ACTIVE", "PAUSED", "COMPLETE", "CANCELLED"]


class DowntimeEntry(BaseModel):
    reason_code: str
    entered_by:  Literal["OPERATOR", "MIRA_AI"] = "OPERATOR"
    notes:       Optional[str] = None


class OEESummaryItem(BaseModel):
    line_id:      str
    line_name:    str
    oee:          float
    availability: float
    performance:  float
    quality:      float
    teep:         Optional[float] = None
    run_state:    str
    ts:           Optional[datetime] = None


class HealthResponse(BaseModel):
    status:  str
    version: str
    db:      str  # "ok" | "unreachable"
