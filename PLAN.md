# PLAN: MES Core — Week 1 (DB Schema + Alembic Migrations)

**Branch:** `feat/mes-week1-db-schema`
**Issue:** Mikecranesync/MIRA#319
**PRD:** `docs/PRD-MES-CORE.md`
**Date:** 2026-04-15

---

## Objective

Stand up the `mes_core` PostgreSQL schema — the foundational data layer for Work Orders, OEE, Machine States, and Downtime Tracking. All subsequent MES weeks depend on this being clean and stable.

## Affected Files

**New:**
- `services/mes/requirements.txt`
- `services/mes/backend/__init__.py`
- `services/mes/backend/config.py`
- `services/mes/backend/database.py`
- `services/mes/backend/main.py`
- `services/mes/backend/models/__init__.py`
- `services/mes/backend/models/db_models.py`
- `services/mes/backend/models/mes_models.py`
- `services/mes/backend/routes/__init__.py`
- `services/mes/backend/routes/health.py`
- `services/mes/alembic.ini`
- `services/mes/alembic/env.py`
- `services/mes/alembic/script.py.mako`
- `services/mes/alembic/versions/0001_initial_mes_schema.py`
- `services/mes/tests/__init__.py`
- `services/mes/tests/conftest.py`
- `services/mes/tests/test_schema.py`
- `infra/scada/mes.Dockerfile`

**Modified:**
- `docker-compose.yml` — add `factorylm-mes-db` (Postgres) and `factorylm-mes` containers

## Approach

1. Introduce SQLAlchemy 2.x + Alembic into `services/mes/` — first time in repo
2. Follow existing FastAPI service pattern from `services/plc-modbus/`
3. DB schema: 7 tables (`lines`, `products`, `work_orders`, `schedules`, `downtime_reasons`, `machine_states`, `oee_snapshots`)
4. Seed `downtime_reasons` (14 codes) and `lines` (2 lines) in initial migration
5. Postgres 16 via Docker — `factorylm-mes-db` container on port 5433 (avoids conflict)
6. FastAPI skeleton with `/api/health` only — full routes come in Week 2+

## Risks

- No Alembic precedent in repo — introducing fresh, so migration is the only baseline
- Python 3.9 system — using `Optional[X]` not `X | None`
- Register map divergence (plc-modbus CLAUDE.md vs main CLAUDE.md) — MES uses main CLAUDE.md register map (authoritative)

## Rollback

```bash
git checkout main
docker compose down factorylm-mes-db factorylm-mes
```

## Verification Steps

```bash
# Start DB
docker compose up factorylm-mes-db -d

# Run migration
cd services/mes
DATABASE_URL="postgresql://mes:meslocal@localhost:5433/mes_core" alembic upgrade head

# Run schema tests
pytest services/mes/tests/test_schema.py -v

# Health check
docker compose up factorylm-mes -d
curl localhost:8300/api/health
```

## Note on Active Focus Window

The main `CLAUDE.md` declares a Revenue Priority focus on V1 Telegram bot. This MES work has been explicitly requested by Mike (2026-04-15 session) as a parallel track. Proceeding with explicit authorization.
