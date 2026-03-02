# Mock Mode API Tester Agent

**Mode:** Jarvis-DevOps-Me (see `docs/jarvis-devops-mode.md`)

You start the plc-modbus service in mock mode and validate all API endpoints return expected responses.

## Your Role

1. Start the server on port 8111 (port 8000 is Qdrant on CHARLIE):
   ```bash
   cd services/plc-modbus
   PYTHONPATH=src:. FACTORYLM_MOCK_MODE=true .venv/bin/python -m factorylm_plc --port 8111 &
   ```
2. Wait 4 seconds for startup
3. Test each endpoint with curl:
   - `GET /api/health` — expect `{"status":"healthy"}`
   - `GET /api/plc/status` — expect response containing "connected"
   - `GET /api/plc/io` — expect response containing coils and registers
   - `GET /api/devices` — expect JSON array response
4. Kill the server process
5. Report pass/fail for each endpoint

## Verification Checklist

- [ ] Server starts without errors on port 8111
- [ ] `/api/health` returns healthy status
- [ ] `/api/plc/status` returns connected
- [ ] `/api/plc/io` returns coils and registers
- [ ] `/api/devices` returns array
- [ ] Server process killed cleanly

## Example

**Input:**
```
Start mock mode and test all API endpoints.
```

**Output:**
```
HEALTH: pass
PLC_STATUS: pass
PLC_IO: pass
DEVICES: pass
RESULT: pass
STATUS: done
```
