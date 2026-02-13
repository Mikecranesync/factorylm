# Factory I/O Bridge

**Last Updated:** 2026-02-13  
**Status:** Working — config-driven, persistent Modbus connection, 5-10 Hz polling

---

## What It Does

The bridge (`sim/factoryio_bridge.py`) reads PLC tags from either:
- **Factory I/O** via Modbus TCP (persistent connection, config-driven tag map)
- **Built-in simulator** (when no Factory I/O available — use `--sim` flag)

It posts each tag snapshot to the Matrix API, which auto-creates incidents on faults.

---

## Usage

```bash
# Factory I/O mode (default — reads from Modbus)
python sim/factoryio_bridge.py

# Simulator mode (no Factory I/O needed)
python sim/factoryio_bridge.py --sim

# High-frequency polling (200ms = 5 Hz)
python sim/factoryio_bridge.py --interval 200

# Custom host (real PLC on network)
python sim/factoryio_bridge.py --plc-host 192.168.1.100 --plc-port 502
```

---

## Factory I/O Modbus Setup (Step-by-Step)

### Step 1: Install and Open Factory I/O
- Download from https://factoryio.com (free trial available)
- Open the application

### Step 2: Load a Scene
- **Recommended:** "Sorting by Height" — has conveyors, photoeye sensors, jams
- **Alternative:** "From A to B" — simpler, one conveyor with sensors
- Go to **File → Scenes** and select your scene

### Step 3: Enable the Modbus TCP Server
1. Go to **File → Drivers**
2. Select **Modbus TCP/IP Server** from the driver list
3. Click **Configuration**
4. Set:
   - **Host:** `127.0.0.1` (or your machine's IP if bridging remotely)
   - **Port:** `502`
5. Click **OK**

### Step 4: Map I/O Points to Modbus Addresses

In the Modbus Configuration window:

| Factory I/O Signal | Modbus Type | Address | FactoryLM Tag |
|-------------------|-------------|---------|---------------|
| Conveyor Motor | Coil | 0 | motor_running |
| Conveyor Running | Coil | 3 | conveyor_running |
| Entry Sensor | Coil | 4 | sensor_1_active |
| Exit Sensor | Coil | 5 | sensor_2_active |
| E-Stop | Coil | 6 | e_stop_active |
| Motor Speed | Holding Register | 100 | motor_speed |
| Motor Current | Holding Register | 101 | motor_current |
| Conveyor Speed | Holding Register | 104 | conveyor_speed |

**Tip:** Not all signals need to be mapped. Start with conveyor_running and sensors — those are enough to demonstrate fault detection.

### Step 5: Start the Scene
- Click the **Play** button (▶) in Factory I/O
- The Modbus server starts automatically when the scene runs

### Step 6: Run the Bridge
```bash
python sim/factoryio_bridge.py
```

You should see:
```
Config loaded from config/factoryio.yaml
Modbus connected to 127.0.0.1:502
Bridge started — posting to http://localhost:8000 every 200ms (5.0 Hz)
```

### Step 7: Trigger a Fault
- In Factory I/O, **manually stop a conveyor** or **block a sensor** with a box
- The bridge detects `fault_alarm=True` and the Matrix API creates an incident
- The Cosmos watcher analyzes it and attaches an insight

---

## Configuration

All settings in `config/factoryio.yaml`:

| Setting | Default | Description |
|---------|---------|-------------|
| `host` | 127.0.0.1 | Modbus TCP host |
| `port` | 502 | Modbus TCP port |
| `matrix_url` | http://localhost:8000 | Matrix API endpoint |
| `interval_ms` | 200 | Poll interval (200ms = 5 Hz) |
| `incident_source` | factoryio | `factoryio` or `sim` |
| `coils` | see file | Coil address → tag name mapping |
| `registers` | see file | Register address → tag name mapping |

Environment variables override CLI args:
- `PLC_HOST` — Modbus TCP host
- `PLC_PORT` — Modbus TCP port
- `MATRIX_URL` — Matrix API URL

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| "pymodbus not installed" | `pip install pymodbus` |
| "Modbus connection failed" | Is Factory I/O running? Is the Modbus driver enabled? |
| Bridge connects but no data | Check tag addresses match your Factory I/O Modbus configuration |
| Tags appear but no incidents | Trigger a fault in Factory I/O (block a sensor, stop motor) |
| High poll_errors count | Reduce polling frequency (increase interval_ms) or check network |

---

## Architecture

```
Factory I/O (Modbus TCP Server :502)
        │ persistent TCP connection
        │ polls coils + registers at 5-10 Hz
        ▼
  factoryio_bridge.py (ModbusReader)
        │ maps raw values to tag names
        │ applies scale factors
        │ HTTP POST /api/tags
        ▼
  Matrix API → auto-creates incidents on fault
        │
        ▼
  Cosmos Watcher → analyzes → HMI shows insight
```
