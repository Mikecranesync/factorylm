# Archive: plc-client-factoryio (V2)

**Archived:** 2026-02-12
**Original version:** 0.3.1
**Original repo:** https://github.com/Mikecranesync/factorylm-plc-client.git
**Submodule commit:** 2a805bd6c30270757fe53f18807678b28d5496fb

---

## What It Was

Factory I/O + Allen-Bradley Micro 820 PLC client library via Modbus TCP (Python 3.9+).

Key features:
- Modbus TCP communication with Micro 820 PLC on port 502
- Factory I/O scene-aware state reading
- `to_llm_context()` method for formatting PLC state for LLM prompts
- MockPLC for testing without hardware
- Connection management with automatic retry/reconnection

## Why It Was Archived

- V2 and V3 (`services/plc-modbus/`) shared 7 identical files
- V2 used the deprecated `slave=` parameter in pymodbus (V3 uses modern `device_id=`)
- V2 was missing `llm4plc.py` (LLM-controlled PLC integration)
- No active code imported from this directory
- Tests migrated to `services/plc-modbus/tests/`
- Was tracked as a git submodule (mode 160000) with no `.gitmodules` entry (orphaned reference)

## Where The Code Lives Now

```
services/plc-modbus/src/factorylm_plc/   ← canonical location
services/plc-modbus/tests/               ← migrated tests
```

## Original Register Map

### Holding Registers (100-105)

| Address | Name           | Description               |
|---------|----------------|---------------------------|
| 100     | motor_speed    | Motor speed 0-100%        |
| 101     | motor_current  | Current in 0.1A           |
| 102     | temperature    | Temp in 0.1°C             |
| 103     | pressure       | Pressure in PSI           |
| 104     | conveyor_speed | Conveyor speed %          |
| 105     | error_code     | Error code (0=none)       |

### Coils (0-6)

| Address | Name             | Description          |
|---------|------------------|----------------------|
| 0       | motor_running    | Motor is running     |
| 1       | motor_stopped    | Motor is stopped     |
| 2       | fault_alarm      | Fault active         |
| 3       | conveyor_running | Conveyor running     |
| 4       | sensor_1_active  | Part at sensor 1     |
| 5       | sensor_2_active  | Part at sensor 2     |
| 6       | e_stop_active    | E-stop pressed       |
