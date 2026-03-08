# FactoryLM Edge Adapter — Architecture & Known Issues

## Overview
The "edge adapter" is a set of files that bridge physical GPIO (Raspberry Pi) and Modbus TCP to the FactoryLM stack.

## File Map

| File | Role |
|------|------|
| `services/plc-modbus/factorylm-edge/edge_server.py` | Modbus TCP **server** on RPi — maps GPIO pins to Modbus coils |
| `services/plc-modbus/factorylm-edge/gpio_mapping.py` | GPIO pin configs for Factory I/O scenes (sorting, pick-place, etc.) |
| `services/plc-modbus/factorylm-edge/config.json` | Default runtime config (inputs/outputs/server) |
| `services/plc-modbus/factorylm-edge/install.sh` | RPi one-command setup (venv + systemd service) |
| `integrations/edge_gateway.py` | Modbus TCP **client** — used by VPS workers to poll PLC registers remotely |
| `workers/edge_gateway_tasks.py` | Celery tasks: health_check (1min), poll_registers (5s), connectivity test |
| `workers/edge_log_watcher.py` | Celery task: watches `/opt/factorylm-sync/edge-logs/` and ingests to InfluxDB |

## Architecture
```
RPi (edge_server.py)          VPS (workers)              PLC Laptop
  GPIO pins                    Celery beat                 Micro 820
  ↕ pymodbus server            ↕ every 5s                  ↕ Modbus TCP
  Modbus TCP :502  ← ← ← edge_gateway.py → → →  plc-modbus API :8001
                     (direct Modbus TCP)           (FastAPI wrapper)
```

## Known Bugs (verified against pymodbus 3.12.0)

### BUG 1: `observability.metrics.write_metric` does not exist (IMPORT CRASH)
`workers/edge_gateway_tasks.py` line 16: `from observability.metrics import write_metric`
The `observability` module lives at `/opt/master_of_puppets/observability/` on the VPS,
but `write_metric` was never implemented. The function is called 12+ times in
`edge_gateway_tasks.py`. This causes an **ImportError on startup** — the Celery worker
can't even register these tasks.

### BUG 2: `integrations/edge_gateway.py` creates new TCP connection per call
`connect_to_edge()` and `read_plc_registers()` each create a fresh `ModbusTcpClient`,
connect, read, close. When `poll_registers` runs every 5s, this means 6+ TCP
connect/disconnect cycles per poll (one per register group). This is:
- Slow (connection overhead dominates)
- Fragile (PLC may refuse rapid reconnects)
- A connection leak risk if exceptions occur between connect and finally

### BUG 3: edge_gateway.py bypasses plc-modbus API entirely
The `integrations/edge_gateway.py` talks directly to the PLC via raw pymodbus,
duplicating the logic in `services/plc-modbus/backend/services/plc_connection.py`.
This means:
- Two independent Modbus connections to the same PLC (conflict risk)
- Different coil/register name mappings
- Health check results invisible to the dashboard
- No benefit from the FastAPI API's connection management

### BUG 4: edge_server.py — `identity.VendorName` attributes may not exist
In pymodbus 3.12, `ModbusDeviceIdentification()` properties changed. Direct attribute
assignment like `identity.VendorName = "FactoryLM"` may silently fail or raise.
Need to verify the 3.12 API for setting identification fields.

### BUG 5: `workers/edge_log_watcher.py` — hardcoded VPS paths
Lines reference `/opt/master_of_puppets` and `/opt/factorylm-sync/edge-logs/`
which only exist on the VPS. This file can't run anywhere else without config changes.

### NOT a bug (verified):
- `ModbusDeviceContext` import: CORRECT for pymodbus 3.12 (was renamed FROM `ModbusSlaveContext`)
- `from pymodbus import ModbusDeviceIdentification`: CORRECT for pymodbus 3.12
- `device_id=` kwarg in `read_holding_registers()`: CORRECT for pymodbus 3.12
- `edge_server.py` imports successfully on Windows without RPi.GPIO (simulation mode)