# PLAN: MES Core — Week 5 (Downtime Tracking)

**Branch:** `feat/mes-week5-downtime`
**Issue:** Mikecranesync/MIRA#323
**PRD:** `docs/PRD-MES-CORE.md §4.4`
**Date:** 2026-04-16
**Depends on:** Weeks 1–4 merged

---

## Objective

Complete the "Core Four" anchor: downtime tracking with three capture modes:
1. **AUTO** — PLC fault code → reason_code (already live via state_poller + state_machine.py)
2. **MANUAL** — operator or MIRA sends a reason_code directly via REST
3. **NLP** — operator or MIRA sends a free-text description → keyword classifier → reason_code

## Affected Files

**New:**
- `services/mes/backend/services/downtime_classifier.py` — pure NLP keyword→reason_code
- `services/mes/backend/routes/downtime.py`              — 3 endpoints
- `services/mes/tests/test_downtime.py`                  — classifier + API tests

**Modified:**
- `services/mes/backend/main.py`                         — include downtime router
- `PLAN.md`                                              — this file

---

## Approach

### 1. NLP Classifier (pure function, no LLM)

`classify_reason(text: str) -> tuple[str, str]`
Returns `(reason_code, confidence)` where confidence is "high" or "low".

Keyword priority table (first match wins):
| Keywords | Reason Code |
|----------|-------------|
| estop / e-stop / emergency stop | E_STOP |
| pm / preventive / scheduled maint | MAINT_PM |
| breakdown / broken / failed / fault | MAINT_BREAKDOWN |
| tooling / tool change | CHANGEOVER_TOOLING |
| changeover / product change / switchover | CHANGEOVER_PRODUCT |
| jam / jammed / stuck / blocked conveyor | JAM |
| starved / no material / empty / feed | STARVED_MATERIAL |
| blocked / downstream / full | BLOCKED_DOWNSTREAM |
| quality / hold / inspection / reject | QUALITY_HOLD |
| overload / overcurrent | OVERLOAD |
| overheat / hot / thermal | OVERHEAT |
| sensor / proximity / photoelectric | SENSOR_FAIL |
| comms / communication / timeout / network | COMMS_FAIL |
fallback → UNKNOWN, confidence="low"

### 2. Endpoints (`downtime.py`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/mes/downtime-reasons` | List all 14 reason codes |
| GET | `/api/mes/lines/{id}/downtime?hours=8` | All DOWN/CHANGEOVER events for line |
| POST | `/api/mes/lines/{id}/downtime` | Attach reason to current open DOWN event |

POST body (two modes):
- Direct: `{ "reason_code": "JAM", "entered_by": "OPERATOR", "notes": "..." }`
- NLP:    `{ "description": "the line is jammed", "entered_by": "MIRA_AI" }`

POST logic:
1. Line must exist → 404
2. Must have an open DOWN/CHANGEOVER state (ended_at IS NULL) → 409 if not
3. If reason_code given: validate it exists → 422 if not
4. If description given: classify → reason_code (fallback to UNKNOWN)
5. UPDATE machine_states SET reason_code=?, entered_by=?, notes=?
6. Return updated event

### 3. Response shape

```python
class DowntimeEventResponse(BaseModel):
    id:           str
    line_id:      str
    state:        str          # DOWN or CHANGEOVER
    reason_code:  Optional[str]
    reason_desc:  Optional[str]  # joined from downtime_reasons
    category:     Optional[str]  # PLANNED / UNPLANNED / EXTERNAL
    entered_by:   str
    notes:        Optional[str]
    started_at:   datetime
    ended_at:     Optional[datetime]
    duration_min: Optional[int]  # None if still open
```

---

## Risks

- POST must find the open DOWN row atomically — use single DB query with
  `ended_at IS NULL AND state IN ('DOWN','CHANGEOVER')` not in-memory cache.
- NLP classifier must never raise — always returns a (code, confidence) tuple.
- If line has multiple open rows (shouldn't happen, but defensive): update only the most recent.

## Rollback

Delete the new files, remove import from main.py. No DB schema changes.

## Verification

1. `pytest tests/test_downtime.py -v` — all new tests pass
2. `pytest tests/ -v` — full suite (66 + new) passes, zero regressions
3. NLP: "the conveyor is jammed" → JAM, "scheduled PM" → MAINT_PM, "e-stop" → E_STOP
4. POST with no open DOWN → 409
