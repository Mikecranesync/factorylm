# Cosmos Cookoff Demo Runbook

**Last Updated:** 2026-02-13  
**Status:** MVP — working end-to-end with stub Cosmos responses

---

## Prerequisites

- Python 3.11+
- pip packages: `fastapi uvicorn httpx pyyaml pymodbus` (install with `pip install fastapi uvicorn httpx pyyaml pymodbus`)
- Factory I/O installed with a conveyor scene loaded (Optional — built-in simulator available)
- If using Factory I/O: Modbus TCP server enabled (Settings → Drivers → Modbus TCP/IP Server)

---

## Quick Start (Simulator Mode — No Hardware Needed)

Open **three terminals**, all from the repo root (`c:\Users\hharp\OneDrive\Desktop\FactoryLM`):

### Terminal 1: Start Matrix API

```bash
python -m uvicorn services.matrix.app:app --host 0.0.0.0 --port 8000
```

Open http://localhost:8000 in your browser — you should see the FactoryLM Matrix dashboard.

### Terminal 2: Start Factory I/O Bridge (Simulator Mode)

```bash
python sim/factoryio_bridge.py --sim --interval 500
```

Tags will start flowing into the Matrix API. The dashboard will show live values.

### Terminal 3: Start Cosmos Watcher

```bash
python cosmos/watcher.py --matrix-url http://localhost:8000 --interval 5
```

The watcher polls for open incidents every 5 seconds.

### Trigger a Fault

In **Terminal 2**, the simulator is running. To inject a fault, stop the bridge (`Ctrl+C`), then run with a fault:

```bash
python sim/factoryio_bridge.py --sim --interval 500
```

Or use the standalone simulator with interactive fault injection:

```bash
# Terminal 2 (alternative): Use interactive simulator + bridge separately
# Terminal 2a: Simulator
python sim/plc_simulator.py --interval 500

# Terminal 2b: Bridge (reads from simulator's SQLite)
# For now, the --sim flag on the bridge does both
```

**Simplest fault injection**: Stop the bridge, start the standalone sim, type `jam`, then restart the bridge.

Or use curl to directly inject a faulted tag:

```bash
curl -X POST http://localhost:8000/api/tags -H "Content-Type: application/json" -d "{\"timestamp\":\"2026-02-13T10:00:00Z\",\"node_id\":\"sim-micro820\",\"motor_running\":true,\"motor_speed\":60,\"motor_current\":8.5,\"temperature\":35.0,\"pressure\":100,\"conveyor_running\":true,\"conveyor_speed\":0,\"sensor_1\":true,\"sensor_2\":false,\"fault_alarm\":true,\"e_stop\":false,\"error_code\":3,\"error_message\":\"Conveyor jam\"}"
```

### Watch the Result

1. **Terminal 3** (Cosmos watcher) will log: `Analyzing incident #1: Conveyor jam`
2. **Browser** (http://localhost:8000): Click on the incident to see the Cosmos Reason 2 insight with root cause, confidence, and suggested checks.

---

## Full Mode (Factory I/O as the Virtual Line)

This path uses Factory I/O as a realistic virtual conveyor system.

### Step 1: Set Up Factory I/O

1. Open Factory I/O
2. Load the **"Sorting by Height"** scene (or "From A to B" for simplicity)
3. Enable the Modbus driver:
   - Go to **File → Drivers → Modbus TCP/IP Server**
   - Click **Configuration** → set Host: `127.0.0.1`, Port: `502`
   - Map I/O points to Modbus addresses (see `docs/factoryio_bridge.md` for the full mapping)
4. Click **Play** (▶) to start the scene

### Step 2: Start the FactoryLM Stack (3 terminals)

```bash
# Terminal 1: Matrix API + Web HMI
python -m uvicorn services.matrix.app:app --host 0.0.0.0 --port 8000

# Terminal 2: Factory I/O Bridge (reads Modbus, posts to Matrix)
python sim/factoryio_bridge.py

# Terminal 3: Cosmos Watcher (analyzes incidents)
python cosmos/watcher.py --interval 5
```

### Step 3: Verify Tags Are Flowing

- Open http://localhost:8000 — the dashboard should show live tag values updating at 5 Hz
- Terminal 2 should log: `Stats: N posted, 0 poll_errors, 0 post_errors, 5.0 posts/sec`

### Step 4: Trigger a Fault in Factory I/O

Choose one:
- **Block a sensor**: drag a box to block the entry photoeye for >3 seconds
- **Stop the conveyor**: manually toggle the conveyor motor off
- **Press E-Stop**: click the emergency stop button in the scene

### Step 5: Watch the Result

1. **Terminal 2** logs: `⚡ FAULT DETECTED: Conveyor jam (error_code=3)`
2. **Terminal 3** logs: `Analyzing incident #1: Conveyor jam`
3. **Browser** (http://localhost:8000): Click the incident to see the Cosmos insight:
   - Summary: "Conveyor jam detected. Material flow interrupted."
   - Root cause: "Physical obstruction in conveyor path"
   - Confidence: 88%
   - Suggested checks: Clear jammed material, inspect photoeyes, check belt tracking

### Step 6: Clear the Fault

- Remove the obstruction in Factory I/O
- Terminal 2 logs: `✅ Fault cleared`
- The conveyor resumes normal operation

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Matrix API won't start | Check port 8000 is free: `netstat -ano \| findstr :8000` |
| Bridge can't connect to Modbus | Verify Factory I/O Modbus server is enabled, check firewall |
| Cosmos watcher says "Cannot reach Matrix API" | Start Matrix API first (Terminal 1) |
| No incidents appearing | Check bridge is posting tags: look for "Posted N snapshots" in Terminal 2 |
| Dashboard shows "Loading..." | Matrix API may not be running — check Terminal 1 |
| `httpx` not found | `pip install httpx` |
| `pymodbus` not found | `pip install pymodbus` (only needed for real Modbus, not sim mode) |

---

## What This Demonstrates

1. **Real-time PLC data ingestion** — tags flow from PLC/simulator → Matrix API
2. **Automatic incident detection** — faults trigger incident creation
3. **AI-powered root cause analysis** — Cosmos Reason 2 (stub) analyzes each incident
4. **Mobile-friendly HMI** — web dashboard at http://localhost:8000 shows live data + insights
5. **Read-only safety** — the system never writes to the PLC

---

## Using the Video Diary for Documentation

The Video Diary system automatically analyzes footage and generates demo clips.

### Review Today's Highlights

```bash
# See top highlights from today
python video/highlight_selector.py --date 2026-02-13 --top 10

# Filter to jam-related events only
python video/highlight_selector.py --event jam --min-score 70
```

### Generate a 30-Second Cookoff Submission Clip

```bash
# Auto-select the best highlights and build a demo reel
python video/short_builder.py --auto --top 5 --output cookoff_demo.mp4 --title "FactoryLM + Cosmos Reason 2"

# Or hand-pick specific clips
python video/short_builder.py --clips 3,7,12 --output jam_diagnosis.mp4 --title "Asynchronous Jam Diagnosis"
```

### Browse in the HMI

Open **http://localhost:8000/video** to:
- See all analyzed clips with scores and captions
- Filter to highlights only
- Click any clip for full Cosmos analysis detail

---

## Architecture (End-to-End Flow)

```
Factory I/O / Simulator
        │ Modbus TCP or built-in sim
        ▼
  factoryio_bridge.py
        │ HTTP POST /api/tags
        ▼
  Matrix API (FastAPI + SQLite)
        │ Auto-creates incidents on fault
        ▼
  cosmos/watcher.py
        │ Polls /api/incidents?status=open
        │ Calls CosmosClient.analyze_incident()
        │ Posts result to /api/insights
        ▼
  Web HMI (http://localhost:8000)
        │ Polls /api/tags + /api/incidents
        │ Shows live tags + incident detail + Cosmos insight
        ▼
  Technician sees root cause + suggested actions
```
