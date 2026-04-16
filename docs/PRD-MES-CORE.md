# PRD: MIRA MES Core — Work Orders, OEE, Downtime, and Scheduling

**Status:** Draft  
**Author:** CHARLIE node  
**Reference:** Walker Reynolds / 4.0 Solutions — 8-Week MES Bootcamp (Session 1, Dec 2024)  
**Source video:** https://youtu.be/pSX4OBr0iyk  
**Target repo:** Mikecranesync/MIRA  
**Priority:** P0 (foundational for v1 factory intelligence)

---

## 1. Problem Statement

MIRA can answer maintenance questions and ingest OEM docs, but it cannot yet tell a technician or manager **what is actually happening on the production floor right now.** There is no:

- Live machine state (running / down / changeover / idle)
- OEE score derived from real PLC data
- Work order lifecycle owned by MIRA
- Scheduled production run tied to a physical line

Walker Reynolds defines MES as the **digital bridge between the shop floor and the boardroom**. The board asks: "Do we need to build a new facility?" The answer lives in OEE and capacity data. Without this layer, MIRA is a knowledge tool, not an execution system. This PRD closes that gap.

---

## 2. Reference Architecture (Walker Reynolds / 4.0 Solutions)

The bootcamp teaches one complete MES stack. We adopt the same logical design and re-implement it on the FactoryLM infrastructure.

### 2.1 Walker's Stack → Our Stack Mapping

| Walker's Component | Walker's Tool | MIRA Equivalent |
|---|---|---|
| MES Platform | Ignition (Inductive Automation) | mira-pipeline (FastAPI) + Open WebUI |
| Database | MySQL | PostgreSQL (new `mes_core` schema) or extend mira.db |
| Scripting | Python within Ignition | Python microservices in `services/mes/` |
| MQTT Broker | EMQx | Existing SCADA MQTT stack (`:502` → `:8001`) |
| Unified Namespace | Ignition UNS | FactoryLM UNS (ISA-95, being built in #312) |
| ERP Integration | Odoo | Atlas CMMS (work-order integration in PR #279) |
| UI | Ignition Vision / Perspective | Open WebUI + mira-web dashboard |
| Machine state source | OPC-UA / Kepware | Modbus PLC driver (`services/plc-modbus/`) |

### 2.2 ISA-95 Namespace Structure (Walker's model, our labels)

```
Site (Lake Wales)
  └── Area (Factory Floor)
        └── Line (Conveyor-1, Sorting-1 ...)
              └── Equipment (VFD-GS10, PLC-Micro820 ...)

Namespaces per line:
  production/
    oee               # computed OEE float 0-1
    performance       # P component
    availability      # A component
    quality           # Q component
    good_count        # parts passing QC
    total_count       # all parts produced
    run_state         # RUNNING | DOWN | CHANGEOVER | IDLE | OFFLINE

  quality/
    reject_count
    reject_reason

  maintenance/
    last_fault_code
    last_fault_ts
    mtbf_hours
    mttr_minutes

  kpis/
    teep              # TEEP = OEE × utilization
    downtime_minutes_today
    custom/           # extensible
```

---

## 3. The Core Four Features (Walker's "Core Four")

Walker Reynolds calls these non-negotiable. Every MES starts here:

1. **Work Orders** — create, assign, track, close
2. **Scheduling** — production runs against a schedule
3. **OEE** — Availability × Performance × Quality, live
4. **Downtime Tracking** — machine states + reason codes

All four must ship together for MIRA to qualify as an MES.

---

## 4. Feature Specifications

### 4.1 Work Orders

**What:** A work order represents a discrete production job: product, target quantity, line, start time, end time.

**Data model:**

```sql
work_orders (
  id            UUID PRIMARY KEY,
  order_number  TEXT UNIQUE,        -- from Atlas CMMS or generated
  product_id    UUID FK,
  line_id       UUID FK,
  target_qty    INTEGER,
  good_qty      INTEGER DEFAULT 0,
  status        ENUM('PENDING','ACTIVE','PAUSED','COMPLETE','CANCELLED'),
  scheduled_start TIMESTAMPTZ,
  actual_start    TIMESTAMPTZ,
  actual_end      TIMESTAMPTZ,
  created_at    TIMESTAMPTZ DEFAULT NOW()
)

products (
  id            UUID PRIMARY KEY,
  sku           TEXT UNIQUE,
  name          TEXT,
  ideal_cycle_sec FLOAT   -- used in Performance OEE calculation
)

lines (
  id            UUID PRIMARY KEY,
  name          TEXT,           -- e.g. "Conveyor-1"
  isa95_path    TEXT,           -- e.g. "lakewales/floor/conveyor-1"
  plc_host      TEXT,           -- e.g. "192.168.1.100"
  plc_port      INTEGER DEFAULT 502
)
```

**Behavior:**
- A technician or MIRA chat can create a work order via REST POST
- Activating a work order broadcasts `ACTIVE` to the UNS topic for that line
- Work order completion auto-calculates final OEE and writes to history
- Atlas CMMS sync: PR #279 already wires work-order creation — this PRD extends it with full lifecycle

---

### 4.2 Production Scheduling

**What:** Schedules define which work order runs on which line during which shift.

**Data model:**

```sql
schedules (
  id            UUID PRIMARY KEY,
  work_order_id UUID FK,
  line_id       UUID FK,
  shift         ENUM('DAY','NIGHT','WEEKEND'),
  planned_start TIMESTAMPTZ,
  planned_end   TIMESTAMPTZ,
  planned_qty   INTEGER
)
```

**Behavior:**
- Scheduler publishes upcoming work orders to UNS `production/schedule` 15 min before start
- Machine operator acknowledges start via MIRA chat or HMI button (Node-RED)
- Schedule adherence = actual_start vs. planned_start, reported in KPI namespace

---

### 4.3 OEE (Overall Equipment Effectiveness)

**The formula:**
```
OEE = Availability × Performance × Quality

Availability = Run Time / Planned Production Time
Performance  = (Ideal Cycle Time × Total Count) / Run Time
Quality      = Good Count / Total Count

TEEP = OEE × (Scheduled Time / Max Possible Time)
```

**Data model — OEE events:**

```sql
oee_snapshots (
  id              UUID PRIMARY KEY,
  line_id         UUID FK,
  work_order_id   UUID FK,
  ts              TIMESTAMPTZ,
  run_time_sec    INTEGER,
  planned_time_sec INTEGER,
  total_count     INTEGER,
  good_count      INTEGER,
  ideal_cycle_sec FLOAT,
  availability    FLOAT,
  performance     FLOAT,
  quality         FLOAT,
  oee             FLOAT,
  teep            FLOAT
)
```

**Calculation service (`services/mes/oee_calculator.py`):**
- Runs every 60s per active line
- Reads PLC counters from Modbus (HR100–HR102 in existing register map)
- Reads downtime events from `machine_state_log`
- Writes snapshot to `oee_snapshots`
- Publishes computed OEE to UNS `production/oee` via MQTT

**OEE thresholds (Walker's benchmarks):**
- World-class OEE: ≥ 85%
- Typical OEE: 40–60%
- Below 40%: systemic problem, trigger MIRA alert

---

### 4.4 Downtime Tracking & Machine States

**The "Core Four" anchor.** Walker emphasizes availability (A) is almost always the bottleneck — not performance (P) or quality (Q).

**Machine state machine:**
```
IDLE → RUNNING → DOWN → IDLE
         ↓
    CHANGEOVER → RUNNING
         ↓
      OFFLINE (PLC unreachable)
```

**Data model:**

```sql
machine_states (
  id          UUID PRIMARY KEY,
  line_id     UUID FK,
  state       ENUM('RUNNING','DOWN','CHANGEOVER','IDLE','OFFLINE'),
  started_at  TIMESTAMPTZ,
  ended_at    TIMESTAMPTZ,
  reason_code TEXT,        -- FK to downtime_reasons
  entered_by  ENUM('PLC','OPERATOR','MIRA_AI')
)

downtime_reasons (
  code        TEXT PRIMARY KEY,
  description TEXT,
  category    ENUM('PLANNED','UNPLANNED','EXTERNAL')
  -- examples: MAINT_PM, MAINT_BREAKDOWN, CHANGEOVER_PRODUCT,
  --           STARVED_MATERIAL, BLOCKED_DOWNSTREAM, QUALITY_HOLD
)
```

**State detection logic:**
- PLC Coil0 (motor_run) = 1 → RUNNING
- PLC Coil2 (fault) = 1 → DOWN
- Motor speed (HR100) = 0 AND no fault → IDLE
- PLC unreachable → OFFLINE
- State transition → write to `machine_states`, publish to UNS

**Downtime reason capture:**
- AUTO: if fault code present in Modbus HR102, map to reason_code via lookup table
- MANUAL: MIRA chat ("the line is down for a tooling change") → NLP → reason_code
- HMI: Node-RED button panel at `:1880/ui` — operator selects reason from list

---

## 5. UDT Definitions (Walker's Week 4 Concept → our Pydantic models)

Walker builds UDTs in Ignition. We use Pydantic dataclasses as the equivalent.

```python
# services/mes/models.py

class LineDataType(BaseModel):
    line_id: str
    isa95_path: str
    run_state: Literal["RUNNING","DOWN","CHANGEOVER","IDLE","OFFLINE"]
    oee: float
    availability: float
    performance: float
    quality: float
    good_count: int
    total_count: int
    active_work_order_id: Optional[str]
    ts: datetime

class CountDispatch(BaseModel):
    line_id: str
    count_type: Literal["GOOD","REJECT","TOTAL"]
    delta: int          # increment since last dispatch
    ts: datetime

class OEEDataType(BaseModel):
    line_id: str
    interval_sec: int
    availability: float
    performance: float
    quality: float
    oee: float
    teep: float
    ts: datetime
```

---

## 6. API Endpoints (new `services/mes/` microservice)

```
POST   /api/mes/work-orders              # create work order
GET    /api/mes/work-orders              # list (filter by status, line)
GET    /api/mes/work-orders/{id}         # detail
PATCH  /api/mes/work-orders/{id}/status  # PENDING→ACTIVE→COMPLETE
GET    /api/mes/lines                    # list configured lines
GET    /api/mes/lines/{id}/state         # current machine state
GET    /api/mes/lines/{id}/oee           # current OEE snapshot
GET    /api/mes/lines/{id}/oee/history   # time-series OEE (last N hours)
GET    /api/mes/lines/{id}/downtime      # downtime events (today)
POST   /api/mes/lines/{id}/downtime      # manual downtime reason entry
GET    /api/mes/oee/summary              # fleet OEE rollup (all lines)
GET    /api/mes/kpis                     # TEEP, downtime_minutes, schedule_adherence
```

Auth: reuse existing PLC API token pattern (Bearer header).

---

## 7. MIRA Chat Integration

Walker's MES has an HMI for operator input. Ours uses MIRA chat.

**New intent handlers in `mira-pipeline/gsd_engine.py`:**

| User says | MIRA does |
|---|---|
| "Start work order W-1042" | POST /api/mes/work-orders/W-1042/status → ACTIVE |
| "Line 1 is down, tooling change" | POST /api/mes/lines/conveyor-1/downtime {reason_code: CHANGEOVER_TOOLING} |
| "What's our OEE today?" | GET /api/mes/oee/summary → format response |
| "How long has line 2 been down?" | GET machine_states WHERE line=2 AND state=DOWN |
| "Complete the current work order" | PATCH /api/mes/work-orders/{active}/status → COMPLETE |

**MIRA knowledge injection (hooks into #24 Vision→RAG loop):**
- On OEE < 60% for > 30 min → inject context into MIRA chat: "Line 1 OEE has dropped to 47%. Longest downtime reason today: MAINT_BREAKDOWN (42 min)."
- On OFFLINE state > 5 min → trigger Telegram alert + MIRA proactive message

---

## 8. Open WebUI Dashboard Integration

Walker's Ignition Vision screens → our Open WebUI + mira-web.

**New views:**
1. **Fleet OEE Board** — all lines, live OEE gauges (A/P/Q breakdown), TEEP
2. **Line Detail** — machine state timeline (Gantt), downtime reasons pie chart, work order progress
3. **Work Order List** — filter by status, line, shift
4. **Downtime Reason Entry** — operator modal (triggered on DOWN state detection)

These extend issues #302 (persistent memory) and #305 (sub-models) — the MIRA PM sub-model should have full MES context.

---

## 9. Database Migration Plan

Existing state: `mira.db` (SQLite, issue #274 bind-mount bug). MES data volume and query patterns require PostgreSQL.

**Migration path:**
1. Fix `mira.db` bind-mount bug (#274) — unblock current SQLite
2. Add `mes_core` schema to existing Postgres (if present) or spin new container in `docker-compose.yml`
3. Alembic migrations for all tables above
4. Do NOT touch existing MIRA tables — additive schema only

**Docker compose addition:**
```yaml
factorylm-mes-db:
  image: postgres:16-alpine
  environment:
    POSTGRES_DB: mes_core
    POSTGRES_USER: mes
    POSTGRES_PASSWORD: ${MES_DB_PASSWORD}
  volumes:
    - mes_db_data:/var/lib/postgresql/data
  ports:
    - "5433:5432"
```

---

## 10. Acceptance Criteria

Each criterion must have deterministic proof (Cluster Law 1):

| # | Criterion | Proof |
|---|---|---|
| 1 | Work order can be created via REST and via MIRA chat | `curl POST /api/mes/work-orders` returns 201; MIRA chat "start WO-001" creates record in DB |
| 2 | Machine state reads from live PLC Modbus | `curl /api/mes/lines/conveyor-1/state` returns RUNNING when Coil0=1 |
| 3 | OEE calculates correctly | Freeze PLC counters at known values, assert OEE = expected within ±0.01 |
| 4 | Downtime event captured on fault | Set Coil2=1 on mock PLC → `machine_states` row appears within 10s |
| 5 | TEEP reported alongside OEE | `GET /api/mes/kpis` includes `teep` field |
| 6 | MIRA chat can query OEE | "What's our OEE today?" returns fleet summary with numeric values |
| 7 | Open WebUI fleet OEE board renders | Navigate to dashboard, all configured lines show live gauges |
| 8 | Work order close writes final OEE to history | Complete WO via API, `oee_snapshots` has record for that WO |
| 9 | Atlas CMMS work orders sync (bidirectional) | Create WO in CMMS → appears in `/api/mes/work-orders`; create via API → appears in CMMS |
| 10 | All tests pass in CI | `pytest services/mes/ -v` green in GitHub Actions |

---

## 11. Out of Scope (v1)

- Advanced scheduling optimization (no ML-based scheduling yet)
- Multi-site / multi-area rollup (single factory floor only)
- Quality inspection integration (QC camera, visual defect detection — future)
- ERP bill-of-materials sync (Odoo — future; Atlas CMMS is sufficient for v1)
- Mobile operator app (Open WebUI mobile is sufficient)

---

## 12. Implementation Plan (8-week mirror of Walker's bootcamp)

| Week | Deliverable | Issues to Create |
|---|---|---|
| 1 | DB schema: PostgreSQL `mes_core`, all tables, Alembic migrations | `feat(mes): database schema v1` |
| 2 | `services/mes/` FastAPI skeleton, line config, Modbus state reader | `feat(mes): machine state service` |
| 3 | OEE calculator service, 60s tick, UNS publish | `feat(mes): oee calculator` |
| 4 | Work order CRUD, scheduling model, Pydantic UDTs | `feat(mes): work order management` |
| 5 | Downtime reason capture (auto + manual + MIRA chat NLP) | `feat(mes): downtime tracking` |
| 6 | Atlas CMMS bidirectional sync | `feat(mes): cmms sync` |
| 7 | Open WebUI fleet dashboard, Line detail view | `feat(mes): owui dashboard` |
| 8 | Full integration test suite, CI green, Acceptance criteria verified | `test(mes): acceptance suite` |

---

## 13. Dependencies / Blockers to Resolve First

- **#274** — Fix `mira.db` bind-mount (affects DB stability)
- **#275** — Fix `PIPELINE_API_KEY` in Doppler (pipeline must be healthy before MES hooks in)
- **#312** — ISA-95 path on knowledge_entries (already merged — MES uses same ISA-95 paths)
- **#279** — Atlas CMMS work-order creation (foundation for bidirectional sync)
- **CHARLIE Nautobot** — restart 5 exited containers (DCIM is source of truth for line topology)

---

## 14. Success Metric

A factory manager opens MIRA and asks: **"Should we run overtime tonight or are we on track?"**

MIRA answers with: current OEE per line, remaining quantity on active work orders, projected completion time based on current performance rate, and whether TEEP indicates hidden capacity.

That answer does not exist today. This PRD makes it possible.
