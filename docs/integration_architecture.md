# Factory LM + Cosmos Integration Architecture

**Cosmos Cookoff 2026 — Feb 26 Deadline**

## Component Status

| Component | Location | Status | Notes |
|-----------|----------|--------|-------|
| Factory I/O | PLC Laptop | ✅ Running | Modbus TCP on 100.72.2.99:502 |
| PLC API | PLC Laptop | ✅ Running | FastAPI on 100.72.2.99:8000 |
| Cosmos Agent | `cosmos/agent.py` | ✅ Code exists | Stub responses working |
| Cosmos Client | `cosmos/client.py` | ✅ Stub ready | Needs real API key |
| Video Pipeline | `video/*.py` | ✅ Code exists | ingester, analyzer, highlight, short_builder |
| Docker Stack | `infra/local/` | ✅ Postgres ready | matrix_dev DB |
| Bridge | `sim/factoryio_bridge.py` | ✅ Code exists | Can poll PLC API or Modbus directly |

## Architecture

```
┌────────────────────────────────────────────────────────────────────────────┐
│                        COSMOS COOKOFF ARCHITECTURE                         │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  PLC LAPTOP (100.72.2.99)                                                  │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                                                                     │   │
│  │  ┌──────────────┐    Modbus TCP    ┌──────────────────────────┐    │   │
│  │  │ Factory I/O  │◄───────────────►│ PLC API (FastAPI)        │    │   │
│  │  │   :502       │    coils/regs    │   :8000                  │    │   │
│  │  │              │                  │                          │    │   │
│  │  │ Sorting by   │                  │ GET /api/health          │    │   │
│  │  │ Height scene │                  │ GET /api/plc/io          │    │   │
│  │  └──────────────┘                  │ GET /api/plc/status      │    │   │
│  │                                    └──────────────────────────┘    │   │
│  │                                              │                      │   │
│  └──────────────────────────────────────────────│──────────────────────┘   │
│                                                 │                          │
│                            Tailscale VPN        │ HTTP polling             │
│                               ▼                 ▼                          │
│  TRAVEL LAPTOP (Coordinator)                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                                                                     │   │
│  │  ┌──────────────────┐    ┌─────────────────┐    ┌───────────────┐  │   │
│  │  │ factoryio_bridge │───►│ Matrix API      │───►│ Postgres      │  │   │
│  │  │ sim/             │    │ (incident store)│    │ matrix_dev    │  │   │
│  │  │                  │    └─────────────────┘    └───────────────┘  │   │
│  │  │ Polls            │            │                                  │   │
│  │  │ 100.72.2.99:8000 │            │ new incidents                   │   │
│  │  └──────────────────┘            ▼                                  │   │
│  │                          ┌─────────────────┐                        │   │
│  │                          │ Cosmos Agent    │                        │   │
│  │                          │ cosmos/agent.py │                        │   │
│  │                          │                 │                        │   │
│  │                          │ Watches for     │                        │   │
│  │                          │ incidents,      │                        │   │
│  │                          │ calls Cosmos API│                        │   │
│  │                          └────────┬────────┘                        │   │
│  │                                   │                                  │   │
│  │                                   ▼                                  │   │
│  │                    ┌──────────────────────────────┐                 │   │
│  │                    │ NVIDIA Cosmos Reason 2 API   │                 │   │
│  │                    │ (Cloud / build.nvidia.com)   │                 │   │
│  │                    │                              │                 │   │
│  │                    │ Analyzes fault + video       │                 │   │
│  │                    │ Returns root cause insight   │                 │   │
│  │                    └──────────────────────────────┘                 │   │
│  │                                                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

## Data Flow

### 1. Live Tag Monitoring
1. Factory I/O runs "Sorting by Height" scene with Modbus TCP server on :502
2. PLC API (`services/plc-modbus`) connects to Factory I/O via pymodbus
3. PLC API exposes live tag data at `GET /api/plc/io`
4. Bridge polls PLC API at 5 Hz (200ms), posts to Matrix API
5. Matrix detects anomalies (jam, overload) → creates incident

### 2. Cosmos Analysis
1. Cosmos Agent watches Matrix for new incidents
2. On new incident: fetches tag history + video clip
3. Calls Cosmos Reason 2 API with fault context
4. Posts insight back to Matrix (root cause, confidence, suggested checks)
5. HMI displays insight to operator

### 3. Video Diary (Async)
1. OBS/ffmpeg captures Factory I/O screen → `recordings/raw/`
2. `video/ingester.py` chunks into 10-30s clips
3. `video/cosmos_analyzer.py` captions each clip via Cosmos
4. `video/highlight_selector.py` marks interesting clips (score > 70)
5. `video/short_builder.py` assembles demo reel

## API Endpoints

### PLC Laptop (100.72.2.99:8000)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Returns `{"status": "healthy", "version": "0.1.0"}` |
| `/api/plc/io` | GET | Returns live coils, inputs, outputs, registers |
| `/api/plc/status` | GET | Returns connection status, uptime |

### Current Live Data (as of 2026-02-13)
```json
{
  "coils": {
    "motor_running": true,
    "fault_alarm": false,
    "conveyor_running": false
  },
  "registers": {
    "motor_speed": 0,
    "motor_current": 0,
    "temperature": 0,
    "error_code": 0
  }
}
```

## Environment Variables

| Variable | Purpose | Current Status |
|----------|---------|----------------|
| `NVIDIA_COSMOS_API_KEY` | Cosmos Reason 2 API | **MISSING** |
| `PLC_HOST` | PLC API host | `100.72.2.99` |
| `MATRIX_URL` | Matrix API URL | `http://localhost:8000` |
| `POSTGRES_*` | DB credentials | Set in docker-compose |

## Next Steps

1. **Get Cosmos API access** — Apply at build.nvidia.com or ask in Cookoff Discord
2. **Start Docker stack** — `cd infra/local && docker-compose up -d`
3. **Run bridge** — `python sim/factoryio_bridge.py` (polls PLC API)
4. **Run Cosmos agent** — `python -m cosmos.agent`
5. **Trigger a jam** in Factory I/O → verify end-to-end insight

## Files Reference

```
factorylm/
├── sim/
│   └── factoryio_bridge.py      # Polls PLC API, posts to Matrix
├── cosmos/
│   ├── agent.py                 # Watches incidents, calls Cosmos
│   ├── client.py                # Cosmos Reason 2 API wrapper (stub ready)
│   ├── watcher.py               # Incident watcher
│   └── models.py                # CosmosInsight dataclass
├── video/
│   ├── ingester.py              # Chunks raw video
│   ├── cosmos_analyzer.py       # Captions via Cosmos
│   ├── highlight_selector.py    # Marks interesting clips
│   └── short_builder.py         # Assembles demo reel
├── services/plc-modbus/
│   └── backend/                 # FastAPI PLC API (running on PLC laptop)
├── config/
│   ├── factoryio.yaml           # Modbus addresses, Matrix URL
│   └── cosmos.yaml              # Cosmos API settings
└── infra/local/
    └── docker-compose.yml       # Postgres for Matrix
```

---

*Generated by Coordinator Agent — 2026-02-13*
