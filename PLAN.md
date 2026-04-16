# PLAN: MES Core — Week 6 (Atlas CMMS Bidirectional Sync)

**Branch:** `feat/mes-week6-cmms-sync`
**Issue:** Mikecranesync/MIRA#324
**PRD:** `docs/PRD-MES-CORE.md §3 (ERP/CMMS Integration)`
**Date:** 2026-04-16
**Depends on:** Weeks 1–5 merged

---

## Objective

Bidirectional sync between the MES work order system and Atlas CMMS
(implemented as a GitHub Gist-based portable work order format — see
`cmms/gist_work_order.py` for the existing pattern).

- **MES → CMMS (outbound)**: POST /api/mes/cmms/sync/{id} pushes a WO as a
  Gist document (Markdown + CSV) readable by any CMMS.
- **CMMS → MES (inbound)**: POST /api/mes/cmms/ingest accepts a CMMS work order
  payload and creates/updates a WO in the MES database.
- `cmms_enabled` config gate: sync is opt-in; tests run with it disabled.

## Affected Files

**New:**
- `services/mes/alembic/versions/0002_add_cmms_ref.py`  — adds cmms_ref + cmms_synced_at to work_orders
- `services/mes/backend/services/cmms_client.py`         — CMMS Gist HTTP adapter
- `services/mes/backend/routes/cmms.py`                  — sync endpoints
- `services/mes/tests/test_cmms.py`                      — unit tests

**Modified:**
- `services/mes/backend/models/db_models.py`             — WorkOrder gets cmms_ref, cmms_synced_at
- `services/mes/backend/config.py`                       — cmms_enabled, cmms_github_token
- `services/mes/backend/main.py`                         — include cmms router
- `PLAN.md`

---

## Approach

### 1. DB migration 0002

Adds to work_orders:
  - `cmms_ref TEXT` — GitHub Gist ID once synced (NULL = not yet pushed)
  - `cmms_synced_at TIMESTAMPTZ` — timestamp of last successful push

### 2. CMMS Client (`cmms_client.py`)

Sync HTTP adapter using `httpx.Client`. Controlled by `settings.cmms_enabled`.
When disabled, `push_work_order()` returns a mock response — no real API calls.

Functions:
- `format_work_order(wo, line_name, product_sku, product_name) -> dict`
  Maps MES WO fields to the CMMS Gist metadata schema.
- `push_work_order(metadata, gist_id=None) -> dict`
  Creates Gist if gist_id is None, updates if provided.
  Returns `{gist_id, gist_url}`.

GitHub Gist API:
  POST  https://api.github.com/gists                 — create
  PATCH https://api.github.com/gists/{gist_id}       — update

### 3. CMMS Routes (`cmms.py`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/mes/cmms/sync/{work_order_id}` | Push WO to CMMS Gist; saves cmms_ref back to DB |
| GET  | `/api/mes/cmms/sync/{work_order_id}` | Return sync status (cmms_ref, cmms_synced_at) |
| POST | `/api/mes/cmms/ingest`              | Import CMMS work order → create/update in MES |

Ingest body resolves product by SKU, line by name. Creates WO as PENDING
with `cmms_ref` already populated (marks it as CMMS-originated).

---

## Risks

- `cmms_enabled=False` must short-circuit cleanly in both sync and ingest paths.
- GitHub token is a secret — never logged or returned in API responses.
- `cmms_ref` uniqueness: if the same WO is synced twice, update the Gist, don't create a second.

## Rollback

Delete new files, remove import from main.py.
Run migration downgrade: `ALTER TABLE work_orders DROP COLUMN cmms_ref; DROP COLUMN cmms_synced_at;`

## Verification

1. `pytest tests/test_cmms.py -v` — all new tests pass
2. `pytest tests/ -v` — full suite (95 + new) passes, zero regressions
3. With cmms_enabled=False: sync endpoint returns 200 with mock gist_id
4. Ingest: POST with valid line/product → WO appears in GET /api/mes/work-orders
