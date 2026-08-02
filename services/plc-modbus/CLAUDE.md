# Claude Context - FactoryLM PLC Client

## Project Overview
LLM-controlled industrial automation using Allen-Bradley Micro 820 PLC with Factory I/O simulation.

## Hardware Configuration
- **PLC:** Allen-Bradley Micro 820 (Firmware v12)
- **PLC IP:** 192.168.1.100
- **PC IP:** 192.168.1.50 / 255.255.255.0
- **Protocol:** Modbus TCP on port 502
- **OPC UA:** Port 4840 (disabled by default, enable in CCW)

## Physical I/O Panel
- 1x 3-position selector switch (Left/Center/Right)
- 1x Momentary pushbutton (illuminated)
- 1x Emergency stop with NC/NO contacts
- 3x Indicator LEDs

## Modbus Address Map (0-based for pymodbus)

### Coils (Bool) — "From A to B" Scene
| Address | Variable | Description |
|---------|----------|-------------|
| **0** | Conveyor | PLC → Factory I/O: belt motor |
| **1** | Emitter | PLC → Factory I/O: item spawner |
| **2** | SensorStart | Factory I/O → PLC: entry sensor |
| **3** | SensorEnd | Factory I/O → PLC: exit sensor |
| **4** | RunCommand | Remote trigger (Telegram/API) |
| 5-6 | (unused) | Available program vars |
| **7** | _IO_EM_DI_00 | 3-pos switch CENTER detect |
| **8** | _IO_EM_DI_01 | E-stop NO contact |
| **9** | _IO_EM_DI_02 | E-stop NC contact (ON when released) |
| **10** | _IO_EM_DI_03 | 3-pos switch RIGHT detect |
| **11** | _IO_EM_DI_04 | Left Pushbutton |
| 12-14 | _IO_EM_DI_05-07 | Unused inputs |
| **15** | _IO_EM_DO_00 | 3-pos indicator LED |
| **16** | _IO_EM_DO_01 | E-stop indicator LED |
| **17** | _IO_EM_DO_03 | Auxiliary output |

### Holding Registers (Int)
| Address | Variable | Description |
|---------|----------|-------------|
| **100** | ItemCount | Items that reached SensorEnd |
| **101** | ConveyorHz | Conveyor VFD frequency, Hz |
| **102** | MotorCurrentX10 | Motor current x10, amps = value / 10 |
| **103** | MotorTempX10 | Motor temperature x10, degC = value / 10 |
| **104** | VFDStatus | VFD status: 0 idle, 1 running, 2 fault |
| **105** | ErrorCode | Active error code |

## Physical Control State Tables

**3-Position Switch:**
| Position | DI_00 | DI_03 | DO_00 |
|----------|-------|-------|-------|
| LEFT | 0 | 0 | 0 |
| CENTER | 1 | 0 | 1 |
| RIGHT | 1 | 1 | 1 |

**E-Stop:**
| State | DI_01 | DI_02 | DO_01 |
|-------|-------|-------|-------|
| Released | 0 | 1 | 0 |
| Pressed | 1 | 0 | 1 |

## Quick Connection (pymodbus 3.11+)
```python
from pymodbus.client import ModbusTcpClient

client = ModbusTcpClient('192.168.1.100', port=502, timeout=3)
client.connect()

# Read all I/O (coils 0-17)
result = client.read_coils(address=0, count=18)
bits = [int(b) for b in result.bits[:18]]

# Physical inputs: bits[7:15]  (DI_00-DI_07)
# Physical outputs: bits[15:18] (DO_00, DO_01, DO_03)

# Write output (note: device_id, not slave)
client.write_coil(address=15, value=True)  # DO_00 ON
```

## Key Files
- `backend/` - FastAPI server with network scanner
- `tools/plc_monitor.py` - Real-time I/O display
- `tools/plc_logger.py` - Async state change logger
- `src/factorylm_plc/` - Core Modbus library
- `factorylm-edge/` - Raspberry Pi edge device (Modbus server + GPIO)
- `docs/WHITEPAPER_LLM_PLC_Integration.md` - Full technical documentation (includes ST case study)

## Quick Commands
```bash
# Real-time I/O monitor
python tools/plc_monitor.py

# Log state changes
python tools/plc_logger.py --duration 60

# Start API server (port 8001)
uvicorn backend.main:app --host 0.0.0.0 --port 8001 --reload

# Network scan
curl -X POST http://localhost:8001/api/setup/scan-network

# Remote: start conveyor
curl -X POST http://100.72.2.99:8001/api/plc/write-coil -H "Content-Type: application/json" -d '{"address": 4, "value": true}'
```

## Session History
- **2026-01-24:** Initial integration complete. PLC recovered, Modbus working.
- **2026-01-25:** FastAPI backend with network scanner. Systematic I/O mapping completed. Real-time monitor and logger tools created. White paper documented.
- **2026-01-25 (PM):** Added ST case study (Appendix C) and Raspberry Pi edge device (Appendix D) to whitepaper. Created factorylm-edge directory with Modbus TCP server code for Pi.
- **2026-02-18:** "From A to B" Factory I/O scene integration. Remapped coils 0-4 for scene (Conveyor, Emitter, SensorStart, SensorEnd, RunCommand). Register 100 = ItemCount (registers 101-105 later carry named VFD telemetry — see register table). Backend port → 8001. ST program + CCW setup docs in `scenes/`.
- **2026-08-02:** #161 repair — `RegisterData` model now matches `REGISTER_NAMES` (named VFD fields ConveyorHz/MotorCurrentX10/MotorTempX10/VFDStatus/ErrorCode survive serialization); register table above updated to document 101-105.
