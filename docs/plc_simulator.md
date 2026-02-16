# PLC Simulator

**Last Updated:** 2026-02-13  
**Status:** Working — standalone simulator for demos and development

---

## What It Does

The PLC simulator (`sim/plc_simulator.py`) generates realistic Allen-Bradley Micro 820 conveyor tag data without requiring real PLC hardware. It:

- Publishes JSON tag snapshots at configurable intervals (100–500ms)
- Stores all snapshots in a local SQLite database (`sim/tags.db`)
- Supports interactive fault injection via stdin
- Uses the same tag names and error codes as the real PLC client (`services/plc-modbus/`)

---

## Quick Start

```bash
# Basic usage (500ms interval, runs forever)
python sim/plc_simulator.py

# Or as a module
python -m sim

# Faster updates (200ms)
python sim/plc_simulator.py --interval 200

# Start with a fault already active
python sim/plc_simulator.py --fault jam

# Run for 60 seconds then stop
python sim/plc_simulator.py --duration 60

# Custom database path
python sim/plc_simulator.py --db /path/to/tags.db
```

---

## Fault Injection

While the simulator is running, type a command and press Enter:

| Command | Error Code | Effect |
|---------|-----------|--------|
| `jam` | 3 | Conveyor jam — belt stops, sensor_1 stuck, motor current spikes |
| `overload` | 1 | Motor overload — current draw doubles |
| `overheat` | 2 | Temperature high — temp ramps toward 95°C |
| `sensor` | 4 | Sensor failure — erratic sensor readings |
| `comms` | 5 | Communication loss |
| `estop` | — | Emergency stop — everything stops |
| `release` | — | Release e-stop, restart all systems |
| `clear` | 0 | Clear all faults, return to normal operation |

---

## Output Format

Each line is a JSON object:

```json
{
  "timestamp": "2026-02-13T14:30:00.123456+00:00",
  "node_id": "sim-micro820",
  "motor_running": true,
  "motor_speed": 60,
  "motor_current": 3.12,
  "temperature": 28.5,
  "pressure": 101,
  "conveyor_running": true,
  "conveyor_speed": 50,
  "sensor_1": false,
  "sensor_2": true,
  "fault_alarm": false,
  "e_stop": false,
  "error_code": 0,
  "error_message": "No error"
}
```

---

## Tag Database

All snapshots are stored in SQLite at `sim/tags.db` (configurable via `--db`).

```sql
-- Query recent tags
SELECT * FROM tag_snapshots ORDER BY id DESC LIMIT 10;

-- Query faults only
SELECT * FROM tag_snapshots WHERE fault_alarm = 1 ORDER BY id DESC;

-- Count by error code
SELECT error_code, error_message, COUNT(*) as count
FROM tag_snapshots WHERE error_code > 0
GROUP BY error_code ORDER BY count DESC;
```

---

## Tag Map (matches real Micro 820)

| Tag | Type | Range | Description |
|-----|------|-------|-------------|
| motor_running | bool | — | Motor energized |
| motor_speed | int | 0–100 | Motor speed (%) |
| motor_current | float | 0–12 | Motor current (A) |
| temperature | float | 22–95 | Process temperature (°C) |
| pressure | int | 90–110 | System pressure (PSI) |
| conveyor_running | bool | — | Conveyor belt active |
| conveyor_speed | int | 0–100 | Conveyor speed (%) |
| sensor_1 | bool | — | Photoeye sensor 1 (part detected) |
| sensor_2 | bool | — | Photoeye sensor 2 (part detected) |
| fault_alarm | bool | — | Any fault active |
| e_stop | bool | — | Emergency stop engaged |
| error_code | int | 0–5 | See error codes table |

---

## Integration with Cosmos Agent

The Cosmos agent (`cosmos/agent.py`) can watch the simulator's SQLite database for faults and automatically analyze them:

```bash
# Terminal 1: Start the simulator
python sim/plc_simulator.py

# Terminal 2: Start the Cosmos agent watcher
python -c "
import asyncio
from cosmos.agent import CosmosAgent
agent = CosmosAgent()
asyncio.run(agent.watch_for_incidents('sim/tags.db'))
"

# Terminal 1: Inject a fault
jam
```

The agent will detect the fault, call CosmosClient.analyze_incident(), and store a CosmosInsight in the `cosmos_insights` table in the same database.
