# Edge Adapter Stack Fix — Resume Prompt

## What Was Done

Fixed the FactoryLM edge adapter stack across 5 files in **factorylm-monorepo** (`C:\Users\hharp\Desktop\factorylm-monorepo`):

### Files Created
1. **`observability/__init__.py`** — `traced`, `track_llm_call`, `track_api_call` stubs (no-op/DEBUG log)
2. **`observability/metrics.py`** — `write_metric(measurement, tags, fields)` with lazy InfluxDB client + log-only fallback. Also has `write_celery_task()` and `write_llm_call()` convenience functions.

### Files Modified
3. **`integrations/edge_gateway.py`** — Full refactor:
   - `EdgeGatewayClient` class: persistent Modbus TCP connection, auto-reconnect on failure
   - `EdgeGatewayAPIClient` class: HTTP client calling plc-modbus FastAPI (`GET /api/plc/io`, `GET /api/plc/status`)
   - `get_client(ip)` factory: picks client based on `EDGE_MODE=modbus|api` env var
   - Module-level convenience functions (`connect_to_edge`, `read_plc_registers`, `health_check`) preserved for backwards compat, now backed by a shared singleton client

4. **`workers/edge_gateway_tasks.py`** — No changes needed; the `from observability.metrics import write_metric` import now resolves to the new module

5. **`workers/edge_log_watcher.py`** — Replaced hardcoded paths:
   - `/opt/master_of_puppets` → `os.getenv("FACTORYLM_ROOT", "/opt/master_of_puppets")`
   - `/opt/factorylm-sync/edge-logs` → `os.getenv("EDGE_LOGS_DIR", "/opt/factorylm-sync/edge-logs")`
   - State dir → `os.getenv("FACTORYLM_STATE_DIR", os.path.join(PROJECT_ROOT, "state"))`

### Verification Results (all passing)
- `from observability.metrics import write_metric` → OK
- `from observability import traced, track_llm_call, track_api_call` → OK
- `EdgeGatewayClient('192.168.1.100')` instantiates → OK
- `EdgeGatewayAPIClient('192.168.1.100')` instantiates → OK
- All edge_gateway_tasks dependency imports resolve → OK
- Full edge_gateway_tasks import fails only on `celery` (not installed locally, expected — runs on VPS)

### Related Files (not modified, for context)
- `services/plc-modbus/factorylm-edge/edge_server.py` — RPi Modbus server (pymodbus 3.12, imports verified OK)
- `services/plc-modbus/factorylm-edge/observability.py` — Edge-local shim (separate from the new monorepo-level package)
- `core/src/factorylm/observability.py` — Core OTel-based tracing (separate from both above)

### What's NOT Done Yet
- No commits created (user didn't ask)
- No VPS deployment
- plc-modbus tests not run (`cd services/plc-modbus && python -m pytest tests/ -v`)
- Live PLC health check not tested
- The three `observability` modules (monorepo root, core, edge) could be consolidated in the future
