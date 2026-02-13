# Cosmos Cookoff Project Plan - Factory LM

**Deadline:** Feb 26, 2026 5 PM PT (13 days from Feb 13)
**Status:** DEV - Core infrastructure verified, API integration next

---

## Live Status (auto-updated)

**Last check:** 2026-02-13 17:49 UTC

### PLC Laptop (100.72.2.99)
- [x] Factory I/O running (PID 14872, port 502)
- [x] PLC API healthy at :8000 (`{"status": "healthy", "version": "0.1.0"}`)
- [x] PLC connected to Factory I/O (ESTABLISHED connection)
- [x] I/O data flowing (`motor_running: true`, coils/registers updating)

### Travel Laptop (Coordinator)
- [x] Full codebase exists (`sim/`, `cosmos/`, `video/`, `services/plc-modbus/`)
- [x] Integration architecture documented (`docs/integration_architecture.md`)
- [x] Cosmos client stub ready for real API (`cosmos/client.py`)
- [ ] Cosmos API credentials available (`NVIDIA_COSMOS_API_KEY` NOT SET)
- [ ] Docker stack running locally

### Blockers
- **BLOCKER**: No Cosmos Reason 2 API key — need to apply at build.nvidia.com

### Estimated time to end-to-end demo
- With stub (no real Cosmos): **Ready now** — just start Docker and bridge
- With real Cosmos API: **+1 day after getting API key**

---

## Milestones

### Week 1 (Feb 13-19): Core Infrastructure
- [x] PLC laptop on Tailscale (100.72.2.99)
- [x] Factory I/O running on PLC laptop
- [x] PLC API running and connected to Factory I/O
- [x] Bridge code exists (`sim/factoryio_bridge.py`)
- [x] Config exists (`config/factoryio.yaml`)
- [x] Cosmos agent code exists (`cosmos/agent.py`, `cosmos/client.py`)
- [x] Video pipeline code exists (`video/*.py`)
- [x] Integration architecture documented
- [ ] Docker stack running (Postgres)
- [ ] Bridge polling PLC API → Matrix
- [ ] End-to-end test: Factory I/O jam → Matrix → Cosmos insight (stub)

### Week 2 (Feb 20-25): Real Cosmos + Demo
- [ ] Get Cosmos Reason 2 API access (NVIDIA Build or AWS)
- [ ] Swap stub for real Cosmos calls in `cosmos/client.py`
- [ ] Accumulate 24-48 hrs of analyzed footage
- [ ] Build 3-minute demo video
- [ ] Polish README and docs for judges

### Feb 26: Submission
- [ ] Project description written
- [ ] Demo video rendered and uploaded
- [ ] GitHub repo public and clean
- [ ] Submit before 5 PM PT

---

## Today's Tasks (Feb 13)

### Completed
- [x] PLC laptop verified running (Factory I/O + API)
- [x] Integration architecture documented
- [x] Repo audit completed

### In Progress
- [ ] **Apply for Cosmos API access** — See Discord message below

### Next Up
- [ ] Start Docker: `cd infra/local && docker-compose up -d`
- [ ] Run bridge: `python sim/factoryio_bridge.py`
- [ ] Trigger test jam in Factory I/O
- [ ] Verify Cosmos stub generates insight

---

## Cosmos API Access — Discord Message

Post this in `#questions` on the Cosmos Cookoff Discord:

> Hi! Working on the **Factory LM** project for the Cookoff. We have Factory I/O simulation + PLC tags flowing via a FastAPI service, and our Cosmos client stub is ready (`cosmos/client.py`).
>
> Need to swap in real **Cosmos Reason 2 API** calls. What's the fastest path to API access?
> - NVIDIA Build (build.nvidia.com)?
> - AWS Marketplace?
> - Local model download?
>
> Any rate limits or usage tiers for competition projects? Thanks!

---

## Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                    COSMOS COOKOFF STACK                                │
├────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  PLC LAPTOP (100.72.2.99)                                              │
│  ┌────────────────────┐    Modbus    ┌───────────────────────────────┐│
│  │ Factory I/O  :502  │◄────────────►│ PLC API (FastAPI)  :8000      ││
│  │ "Sorting by Height"│   coils/regs │ GET /api/plc/io               ││
│  └────────────────────┘              │ GET /api/health               ││
│                                      └───────────────┬───────────────┘│
│                                                      │                 │
│                               Tailscale              │ HTTP            │
│                                  ▼                   ▼                 │
│  TRAVEL LAPTOP (Coordinator)                                           │
│  ┌─────────────────┐    ┌──────────────┐    ┌───────────────────────┐ │
│  │ factoryio_bridge│───►│ Matrix API   │───►│ Postgres (matrix_dev) │ │
│  │ polls :8000     │    │ incidents    │    │ :5432                 │ │
│  └─────────────────┘    └──────┬───────┘    └───────────────────────┘ │
│                                │                                       │
│                                ▼                                       │
│                        ┌──────────────┐                                │
│                        │ Cosmos Agent │────► Cosmos Reason 2 API       │
│                        │ cosmos/      │      (NVIDIA Cloud)            │
│                        └──────────────┘                                │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
```

---

## Key Files

| File | Purpose |
|------|---------|
| `sim/factoryio_bridge.py` | Polls PLC API, posts to Matrix |
| `config/factoryio.yaml` | Modbus addresses, Matrix URL |
| `cosmos/agent.py` | Watches incidents, calls Cosmos |
| `cosmos/client.py` | Cosmos API wrapper (stub → real) |
| `video/*.py` | Video diary pipeline |
| `infra/local/docker-compose.yml` | Postgres stack |
| `docs/integration_architecture.md` | Full architecture doc |

---

## Environment Variables

```bash
# Required for real Cosmos (not stub)
export NVIDIA_COSMOS_API_KEY="your-key-here"

# PLC connection (defaults work for our setup)
export PLC_HOST="100.72.2.99"
export MATRIX_URL="http://localhost:8000"
```

---

*Last updated: 2026-02-13 17:50 UTC by coordinator bot*
