# PLAN: MES Core — Week 4 (Work Orders + Scheduling + TEEP)

**Branch:** `feat/mes-week4-work-orders`
**Issue:** Mikecranesync/MIRA#322
**PRD:** `docs/PRD-MES-CORE.md`
**Date:** 2026-04-16
**Depends on:** Week 3 (feat/mes-week3-oee-calculator) merged

---

## Objective

Wire work orders into the MES: create/list/detail/transition endpoints,
expose schedule-aware TEEP (utilisation = scheduled_time / calendar_time),
and update Pydantic UDTs (LineDataType, CountDispatch, OEEDataType) to be
the standard payload shape across all MES responses.

## Affected Files

**New:**
- `services/mes/backend/routes/work_orders.py`  — CRUD + status transitions
- `services/mes/tests/test_work_orders.py`       — unit tests (mocked DB)

**Modified:**
- `services/mes/backend/models/mes_models.py`    — finalise UDTs, add WorkOrder schemas
- `services/mes/backend/services/oee_calculator.py` — TEEP uses schedule utilisation
- `services/mes/backend/main.py`                 — include work_orders router
- `PLAN.md`                                      — this file

---

## Approach

### 1. Work Order Routes (`work_orders.py`)

Four endpoints:

| Method | Path | Action |
|--------|------|--------|
| POST   | `/api/mes/work-orders` | Create — status defaults to PENDING |
| GET    | `/api/mes/work-orders` | List — filter by `?line_id=` and/or `?status=` |
| GET    | `/api/mes/work-orders/{id}` | Detail |
| PATCH  | `/api/mes/work-orders/{id}/status` | Transition: PENDING→ACTIVE→COMPLETE / CANCELLED |

Transition rules (enforced server-side):
- PENDING  → ACTIVE    (start the job)
- ACTIVE   → COMPLETE  (job done)
- ACTIVE   → CANCELLED
- PENDING  → CANCELLED

One line can only have **one ACTIVE work order at a time** — enforced with a
409 Conflict response.

### 2. Schedule-Aware TEEP

TEEP = OEE × Utilisation
Utilisation = scheduled_minutes_in_period / calendar_minutes_in_period

`compute_oee()` gains an optional `utilisation` param (default 1.0, preserving
Week 3 behaviour). The tick loop queries the `schedules` table for the active
shift and passes the utilisation factor.

Until schedules are seeded, utilisation stays 1.0 — no regression.

### 3. Pydantic UDTs (mes_models.py)

Finalise:
- `LineDataType`   — full live status payload
- `CountDispatch`  — part count event
- `OEEDataType`    — OEE snapshot shape (matches DB + API)
- `WorkOrderCreate`, `WorkOrderResponse`, `WorkOrderStatusUpdate`

---

## Risks

- One-ACTIVE-per-line constraint must be checked atomically — use DB query
  inside the same transaction, not an in-memory cache.
- `compute_oee()` signature change adds `utilisation` param — must be
  keyword-only with a default so Week 3 callers need zero changes.

## Rollback

Revert this branch. No DB migrations needed — all tables were created in
Week 1. Work order data is additive.

## Verification Steps

1. `pytest tests/test_work_orders.py -v` — all new tests pass
2. `pytest tests/ -v` — full suite (48 + new) passes, zero regressions
3. Manually: POST work order → PATCH to ACTIVE → OEE tick uses correct ideal_cycle_sec
4. Manually: attempt second ACTIVE work order on same line → 409
