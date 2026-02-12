# ⚠️ DEPRECATED — Do Not Use

This directory (`plc-client/`) is the **V1 prototype** of the FactoryLM PLC client library.

**It has been superseded by:** `services/plc-modbus/src/factorylm_plc/`

## Why

- V1 uses an older subdirectory structure (`modbus/`, `plc/`) that was refactored into a flat layout
- V1 uses the deprecated `slave=` parameter in pymodbus (modern pymodbus 3.11+ uses `device_id=`)
- V1 is missing key modules: `connection_manager`, `factory_io`, `factory`, `llm4plc`
- No active code imports from this directory

## Canonical location

```
services/plc-modbus/src/factorylm_plc/   ← USE THIS
```

That version has:
- Modern pymodbus API (`device_id=`)
- FactoryIO simulator support
- Connection manager with retry/reconnect
- LLM-controlled PLC integration (`llm4plc.py`)
- Active consumers (backend API, CLI tools)

## Tests

The tests in `plc-client/tests/` may still contain useful test patterns.
Consider migrating valuable tests to `services/plc-modbus/` before deleting this directory.

---

*Deprecated: 2026-02-12 — See docs/Architecture.md for details.*
