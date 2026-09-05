# PLAN: Approved sellable-app direction — September 5, 2026

**Slice:** `FLM-APP-NORTH-STAR-2026-09-05`
**Branch:** `docs/sellable-app-north-star-2026-09-05`
**Local tracking issue:** #227
**Product plan:** [Unified delivery](docs/product/2026-09-05-sellable-app-alignment.md)

## Objective and scope

Save Mike's approved clean interface direction in both active repositories and reconcile the documents read at session start. The existing mobile app is the product; MIRA is the assistant; infrastructure supports customer outcomes. This slice changes product documentation only.

## Affected files and approach

- Shared `NORTH_STAR.md` and `docs/product/2026-09-05-sellable-app-alignment.md` in both repos.
- README and agent product summaries; preserve runtime safety/provider/release constraints.
- MIRA strategy/project brief and decision-history snapshots; wiki continuity and index.
- factorylm session memory; retain the previous execution plan below as historical context.

## Execution checklist

- [x] Inspect clean isolated checkout, current main, open PR filenames, and durable claim.
- [x] Write shared product direction, delivery sequence, and repository responsibility.
- [x] Reconcile entry-point priorities and preserve historical context without changing runtime rules.
- [x] Verify scoped diff, mirror equality, links, and available repository checks; limitations below.
- Publication task: commit and publish paired branches, open review PRs, and record exact results in the linked tracking issues.
- [ ] Obtain required exact-commit review before merge readiness; merge/deploy remain separate gates.

## Risks and verification

Main risk: a future session mistakes product priority for permission to bypass a runtime gate or start a competing app. The documents distinguish those boundaries explicitly. Check mirrored content, unchanged protected policy sections, markdown links, scope, and `git diff --check`. Run the applicable available repository checks and report missing dependencies honestly; documentation checks do not prove app behavior.

## Verification result for this documentation slice

Staged diff/whitespace, identical mirrored content, new relative links, historical wording preservation, and unchanged protected policy sections passed. A limited added-line credential-pattern check found no matches; this is not a substitute for gitleaks. The MIRA pre-commit hook completed with gitleaks skipped because the binary is unavailable. FactoryLM core and plc-modbus pytest commands were attempted but could not start because pytest is not installed. The required adversarial lane needs unavailable `gh` and `codex` CLIs; review remains pending. No runtime or deployment success is claimed. Exact commits, CI, and publication outcomes are recorded on the paired issues/PRs.

## Rollback

Before merge, close or revise these isolated documentation PRs. After an approved merge, revert the documentation commit through the normal review path. Historical source text remains in Git and MIRA's decision-history snapshots. No runtime, data migration, installed app, or environment changes require rollback in this slice.

---

## Previous execution plan — preserved historical context

The plan below belongs to an earlier workstream. Its status and priority must be refreshed; it does not supersede the approved north star or authorize a new action.

# PLAN: MES Core — Week 2 (Modbus Machine State Reader)

**Branch:** `feat/mes-week2-state-reader`
**Issue:** Mikecranesync/MIRA#320
**PRD:** `docs/PRD-MES-CORE.md`
**Date:** 2026-04-15
**Depends on:** Week 1 (feat/mes-week1-db-schema) merged

---

## Objective

Build the machine state reader: a background poller that reads the plc-modbus HTTP API every 5 seconds per configured line, detects state transitions (RUNNING/DOWN/IDLE/OFFLINE), writes them to `machine_states`, and exposes `GET /api/mes/lines` and `GET /api/mes/lines/{id}/state` REST endpoints.

## Affected Files

**New:**
- `services/mes/backend/services/__init__.py`
- `services/mes/backend/services/plc_client.py`    — async HTTP client wrapping plc-modbus
- `services/mes/backend/services/state_machine.py` — pure state detection from IO snapshot
- `services/mes/backend/services/state_poller.py`  — asyncio background poll loop
- `services/mes/backend/routes/lines.py`           — GET /api/mes/lines, GET /lines/{id}/state
- `services/mes/tests/test_machine_states.py`      — 10 unit tests, all mocked

**Modified:**
- `services/mes/requirements.txt`  — add httpx
- `services/mes/backend/config.py` — add plc_modbus_url setting
- `services/mes/backend/main.py`   — wire poller into lifespan, add lines router
- `docker-compose.yml`             — add PLC_MODBUS_URL env to mes container

## Approach

1. `plc_client.py` — thin async wrapper around `GET /api/plc/io` (httpx). Raises `PLCOfflineError` on timeout/connection failure so caller can set OFFLINE state.
2. `state_machine.py` — pure function `detect_state(io_data)` → `(MachineStateEnum, reason_code | None)`. Derived from `VFDStatus` and `ErrorCode` registers. No DB or network calls — fully testable without mocks.
3. `state_poller.py` — asyncio task, one iteration per line every 5s. Maintains in-memory cache to avoid DB reads on every tick. Writes to `machine_states` only on transition.
4. `lines.py` routes — two endpoints: list all lines (from DB), get current state (from in-memory cache + last DB row).
5. `main.py` lifespan — start poller task on startup, cancel on shutdown.

State transition write: close open row (`ended_at = NOW()`), insert new row.

## State Machine

```
IO: VFDStatus=1, ErrorCode=0  → RUNNING
IO: VFDStatus=2 OR ErrorCode>0 → DOWN  (reason_code from ErrorCode map)
IO: VFDStatus=0, ErrorCode=0  → IDLE
HTTP failure / timeout         → OFFLINE
```

## ErrorCode → reason_code map

```python
{1: "OVERLOAD", 2: "OVERHEAT", 3: "SENSOR_FAIL", 4: "JAM", 7: "E_STOP"}
```

## Risks

- plc-modbus in mock mode returns VFDStatus=0 at rest — poller sees IDLE immediately (expected)
- Multiple lines share one plc-modbus service currently — same io_data, different `line_id` rows

## Rollback

```bash
git checkout feat/mes-week1-db-schema
```

## Verification Steps

```bash
# Unit tests (no docker needed)
cd services/mes && pytest tests/test_machine_states.py -v

# Integration: start stack, check state endpoint
docker compose up mes-db mes plc-modbus -d
curl localhost:8300/api/mes/lines
curl localhost:8300/api/mes/lines/<id>/state

# Inject a fault and verify DB transition
curl -X POST localhost:8001/api/plc/mock/fault -H "Content-Type: application/json" -d '{"fault_type":"jam"}'
sleep 8
curl localhost:8300/api/mes/lines/<id>/state  # should show DOWN / JAM
```

## Note on Active Focus Window

Explicitly authorized by Mike (2026-04-15 session).
