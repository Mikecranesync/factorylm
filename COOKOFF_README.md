# 🏭 FactoryLM — Physical AI for Industrial Equipment

**NVIDIA Cosmos Cookoff 2026 Entry**

FactoryLM connects to real PLC hardware (Allen-Bradley Micro 820) via Modbus TCP, streams live sensor data through an intelligent pipeline, and uses **NVIDIA Cosmos Reason 2** to diagnose equipment faults from video + sensor data — delivering root-cause analysis to the operator in seconds.

> **Read-only by design.** FactoryLM never writes to PLCs. It observes, reasons, and advises.

---

## 🎬 Demo

**Pipeline in action:**

```
Factory I/O Simulation → Modbus TCP → Matrix API → Cosmos Reason 2 → Diagnosis
         │                                                              │
         └──────────────── Physical AI Feedback Loop ──────────────────┘
```

1. **Conveyor jam occurs** in Factory I/O simulation (or real PLC)
2. Bridge detects `fault_alarm=true, error_code=3` via Modbus polling at 2 Hz
3. Matrix API auto-creates an incident with full tag snapshot
4. Cosmos Watcher picks up the incident, sends sensor context to **Cosmos Reason 2**
5. AI returns: root cause, confidence score, reasoning, and suggested checks
6. Operator sees the diagnosis on the **web HMI dashboard** within seconds

---

## 🧠 How Cosmos Reason 2 Is Used

FactoryLM sends **structured incident bundles** to Cosmos Reason 2 containing:

- **Live PLC tag data**: motor current, temperature, conveyor speed, sensor states, error codes
- **Factory floor video** (when available): timestamped clips from the incident window
- **Operational context**: equipment type, node ID, historical fault patterns

Cosmos Reason 2 returns a **structured diagnosis**:

```json
{
  "summary": "Conveyor jam detected. Material flow interrupted.",
  "root_cause": "Physical obstruction in conveyor path",
  "confidence": 0.88,
  "reasoning": "Conveyor motor drawing current but belt speed is zero with photoeye blocked — classic jam signature.",
  "suggested_checks": [
    "Clear jammed material from conveyor path",
    "Inspect photoeye sensors for alignment",
    "Check conveyor belt tracking",
    "Verify guide rail spacing"
  ]
}
```

The system handles **5 fault types**: motor overload, high temperature, conveyor jam, sensor failure, and communication loss — each with context-aware analysis.

> **Note — Demo scenario:** The conveyor jam / motor paradox response shown above (motor energized, belt speed zero, `error_code=3`) is a pre-defined stub response used when no `NVIDIA_COSMOS_API_KEY` is set. It is not detected by live PLC register correlation. In production, the system would compare the `motor_running` and `speed_feedback` registers in real time to flag this condition without relying on a pre-set error code.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  PLC / Factory I/O                                              │
│  ┌──────────────┐    Modbus TCP    ┌─────────────────────────┐ │
│  │ Factory I/O  │◄───────────────►│ PLC API (FastAPI)       │ │
│  │ Conveyor Sim │  coils/registers │ GET /api/plc/io         │ │
│  └──────────────┘                  └───────────┬─────────────┘ │
│                                                │ HTTP           │
│                            Tailscale           ▼               │
│  ┌─────────────────┐    ┌──────────────────────────────┐       │
│  │ factoryio_bridge│───►│ Matrix API + Web HMI         │       │
│  │ 2 Hz polling    │    │ Tag ingestion, incidents,     │       │
│  └─────────────────┘    │ auto-incident creation        │       │
│                         └──────────────┬───────────────┘       │
│                                        ▼                        │
│                         ┌──────────────────────────────┐       │
│                         │ Cosmos Watcher               │       │
│                         │ Polls for open incidents     │       │
│                         │ → CosmosClient.analyze()     │       │
│                         │ → Stores insight in Matrix   │       │
│                         └──────────────────────────────┘       │
│                                        │                        │
│                                        ▼                        │
│                         ┌──────────────────────────────┐       │
│                         │ NVIDIA Cosmos Reason 2 API   │       │
│                         │ integrate.api.nvidia.com     │       │
│                         └──────────────────────────────┘       │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- pip packages: `fastapi uvicorn httpx pyyaml`
- Optional: `pymodbus` (only for real Modbus/Factory I/O connections)

### Run the full pipeline (3 terminals)

```bash
# Terminal 1: Start Matrix API + Web Dashboard
python -m uvicorn services.matrix.app:app --host 0.0.0.0 --port 8000

# Terminal 2: Start Factory I/O Bridge (simulator mode)
python sim/factoryio_bridge.py --sim --interval 500

# Terminal 3: Start Cosmos Watcher (analyzes incidents automatically)
python cosmos/watcher.py --matrix-url http://localhost:8000 --interval 5
```

Open **http://localhost:8000** to see the live dashboard.

### Trigger a fault

POST a faulted tag to create an incident:

```bash
curl -X POST http://localhost:8000/api/tags -H "Content-Type: application/json" \
  -d '{"timestamp":"2026-02-17T10:00:00Z","node_id":"sim-micro820","motor_running":true,"motor_speed":60,"motor_current":8.5,"temperature":35.0,"pressure":100,"conveyor_running":true,"conveyor_speed":0,"sensor_1":true,"sensor_2":false,"fault_alarm":true,"e_stop":false,"error_code":3,"error_message":"Conveyor jam"}'
```

> **Demo scenario — motor paradox (`error_code=3`):** When no `NVIDIA_COSMOS_API_KEY` is set, this returns a pre-defined stub response. The diagnosis ("motor energized, belt speed zero") is a hardcoded example, not live PLC register correlation. In production, the bridge would detect this condition by comparing `motor_running` and `conveyor_speed` registers dynamically.

The Cosmos Watcher will automatically analyze the incident and the dashboard will show the AI diagnosis.

### Run the smoke test

```bash
python scripts/smoke_test.py
```

Verifies the full pipeline end-to-end: Matrix API → tag ingestion → incident creation → Cosmos analysis → insight storage. All 6 steps should pass in under 5 seconds.

---

## 📁 Key Files

| File | Purpose |
|------|---------|
| `services/matrix/app.py` | Matrix API — tag ingestion, incidents, insights, web HMI |
| `cosmos/client.py` | Cosmos Reason 2 API client with Llama 3.1 fallback |
| `cosmos/watcher.py` | Polls Matrix for incidents, analyzes via Cosmos |
| `sim/factoryio_bridge.py` | PLC/simulator → Matrix bridge (Modbus or sim) |
| `sim/plc_simulator.py` | Realistic PLC simulator with fault injection |
| `cosmos/agent.py` | Async agent for SQLite-based incident watching |
| `services/discord-adapter/bot.py` | Discord community bot |
| `scripts/smoke_test.py` | Automated end-to-end pipeline test |
| `config/factoryio.yaml` | Modbus address mapping |

---

## 🔧 Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `NVIDIA_COSMOS_API_KEY` | For real AI | Cosmos Reason 2 API key from build.nvidia.com |
| `PLC_HOST` | No | PLC/Factory I/O IP (default: 127.0.0.1) |
| `MATRIX_URL` | No | Matrix API URL (default: http://localhost:8000) |
| `MATRIX_DB_PATH` | No | SQLite DB path (default: matrix.db) |

Without `NVIDIA_COSMOS_API_KEY`, the system uses intelligent stub responses that mimic real Cosmos output — suitable for demos and testing.

---

## 🏭 About FactoryLM

FactoryLM is a **4-layer intelligence stack** for industrial automation:

| Layer | What | Example |
|-------|------|---------|
| **Layer 0** | Deterministic code + knowledge base | Tag mappings, alarm thresholds |
| **Layer 1** | Edge LLM | Local fault classification |
| **Layer 2** | Local GPU | On-premise video analysis |
| **Layer 3** | Cloud AI (Cosmos Reason 2) | Multi-modal root-cause analysis |

Intelligence flows **downward** — the goal is to encode AI learnings into deterministic rules over time, requiring less AI for common scenarios.

---

## 👤 Team

**Mike Crane** — Solo builder. Industrial automation background + AI. Building the bridge between PLCs and language models.

- GitHub: [@Mikecranesync](https://github.com/Mikecranesync)
- Architecture maps: [Network Diagrams](https://gist.github.com/Mikecranesync/e8f95da626fd0b4adcb8df13bb62ba96)

---

## 📜 License

MIT
