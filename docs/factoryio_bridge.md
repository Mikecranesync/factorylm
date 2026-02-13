# Factory I/O Bridge

**Last Updated:** 2026-02-13  
**Status:** Working — supports both real Modbus and built-in simulator

---

## What It Does

The bridge (`sim/factoryio_bridge.py`) reads PLC tags from either:
- **Factory I/O** via Modbus TCP (when Factory I/O is running with Modbus server enabled)
- **Built-in simulator** (when no Factory I/O available — use `--sim` flag)

It then POSTs each tag snapshot to the Matrix API at configurable intervals.

---

## Usage

```bash
# Simulator mode (no Factory I/O needed)
python sim/factoryio_bridge.py --sim

# Real Modbus (Factory I/O running)
python sim/factoryio_bridge.py --plc-host 127.0.0.1 --plc-port 502

# Custom Matrix API URL and interval
python sim/factoryio_bridge.py --sim --matrix-url http://localhost:8000 --interval 200
```

---

## Factory I/O Setup

1. Install Factory I/O from https://factoryio.com
2. Open a scene (e.g., "Sorting by Height", "From A to B")
3. Go to **Settings → Drivers → Modbus TCP/IP Server**
4. Enable the server (default: `127.0.0.1:502`)
5. Map I/O tags to the standard addresses in `config/factoryio.yaml`

### Tag Address Map

| Register | Tag | Description |
|----------|-----|-------------|
| Coil 0 | motor_running | Main motor state |
| Coil 2 | fault_alarm | Any fault active |
| Coil 3 | conveyor_running | Belt running |
| Coil 4-5 | sensor_1, sensor_2 | Photoeye sensors |
| Coil 6 | e_stop | Emergency stop |
| Reg 100 | motor_speed | Speed (0-100%) |
| Reg 101 | motor_current | Current (raw ÷ 10 = Amps) |
| Reg 102 | temperature | Temp (raw ÷ 10 = °C) |
| Reg 103 | pressure | Pressure (PSI) |
| Reg 104 | conveyor_speed | Belt speed (0-100%) |
| Reg 105 | error_code | 0=OK, 1=Overload, 2=Overheat, 3=Jam, 4=Sensor, 5=Comms |

---

## Configuration

See `config/factoryio.yaml` for connection settings and tag mapping.

Environment variables (override CLI args):
- `PLC_HOST` — Modbus TCP host (default: 127.0.0.1)
- `PLC_PORT` — Modbus TCP port (default: 502)
- `MATRIX_URL` — Matrix API URL (default: http://localhost:8000)
