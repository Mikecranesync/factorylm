# FactoryLM Cosmos Demo — Start Guide

> Step-by-step runbook to light up the full Cosmos demo pipeline.
> Celery simulator pumps realistic PLC data → Matrix API → PLC Reader dashboard + Cosmos Watcher.

---

## Network

| Machine | Tailscale IP | Role |
|---------|-------------|------|
| Mac Mini | 100.108.19.94 | Celery workers, PLC Reader :8080, Redis |
| PLC Laptop | 100.72.2.99 | Matrix API :8001, Jarvis Node :8765, PLC |

## Prerequisites (all already installed)

- Redis running on Mac Mini (`redis-cli ping` → PONG)
- Matrix API running on PLC Laptop at :8001
- Python 3.11+ with venvs

---

## Start Sequence

### Step 1 — Verify infrastructure

```bash
redis-cli ping                                    # → PONG
curl -s http://100.72.2.99:8001/api/health        # → {"status":"ok"}
```

### Step 2 — Stop the real bridge (posting zeros)

```bash
curl -s -X POST http://100.72.2.99:8765/shell \
  -H 'Content-Type: application/json' \
  -d '{"command":"pkill -f factoryio_bridge","timeout":5}'
```

### Step 3 — Start Celery worker (Terminal 1)

```bash
cd ~/factorylm
celery -A workers.celery_app worker \
    --loglevel=info \
    --concurrency=2 \
    -Q celery \
    -n sim@%h
```

### Step 4 — Start Celery beat (Terminal 2)

```bash
cd ~/factorylm
celery -A workers.celery_app beat --loglevel=info
```

### Step 5 — Verify data flowing

```bash
curl -s http://100.72.2.99:8001/api/tags?limit=1 | python3 -m json.tool
# → node_id: "sim-celery", motor_running: true, motor_speed: 60...
```

### Step 6 — Open PLC Reader dashboard

```
http://100.108.19.94:8080
```

Mode badge cycles: IDLE → RUNNING → E\_STOP → FAULT (auto-cycling)

### Step 7 (optional) — Start Cosmos Watcher (Terminal 3)

```bash
cd ~/factorylm
python cosmos/watcher.py \
    --matrix-url http://100.72.2.99:8001 \
    --interval 5
```

Analyzes incidents, posts insights, sends alerts.

### Step 8 (optional) — Open Matrix Web HMI

```
http://100.72.2.99:8001
```

Live tags + incident list + Cosmos insights.

---

## Demo Flow (auto, hands-free)

```
0:00  ─── IDLE ──────────── motor on, speed 60, temp ~25°, all normal
0:15  ─── RAMP UP ────────── speed climbing to 80, current rising
0:20  ─── FULL SPEED ─────── speed 80, sensors toggle, temp → 40°
0:40  ─── E-STOP           ── everything stops, Discord #alerts fires
                              Cosmos: "Emergency stop engaged..."
0:48  ─── RECOVERY ────────── e-stop cleared, motor restarts
0:53  ─── FULL SPEED ─────── back to normal running
1:13  ─── FAULT            ── conveyor jam! speed=0, current spikes
                              Cosmos: "Conveyor jam detected..."
                              Discord: red embed in #alerts
1:21  ─── CLEAR ───────────── fault cleared, resume normal
1:26  ─── IDLE ──────────── cycle repeats
```

---

## Manual Fault Injection

```bash
# E-stop
celery -A workers.celery_app call simulator.inject --args='["estop"]'

# Conveyor jam
celery -A workers.celery_app call simulator.inject --args='["jam"]'

# Motor overload
celery -A workers.celery_app call simulator.inject --args='["overload"]'

# Clear all faults
celery -A workers.celery_app call simulator.inject --args='["clear"]'

# Release e-stop
celery -A workers.celery_app call simulator.inject --args='["release"]'

# Resume auto-cycle
celery -A workers.celery_app call simulator.inject --args='["resume"]'
```

---

## Troubleshooting

**"No module 'workers.plc\_simulator\_tasks'"**
→ Run from `~/factorylm` (repo root), not a subdirectory

**"Connection refused" on Matrix API**
→ Check PLC Laptop: `curl http://100.72.2.99:8001/api/health`

**Dashboard shows zeros instead of sim data**
→ Real bridge still running? `pkill -f factoryio_bridge` on PLC Laptop
→ Check celery beat logs for `simulator.tick` scheduling

**Incidents not appearing**
→ Wait for fault\_jam phase (~53s into cycle)
→ Or manually: `celery call simulator.inject --args='["jam"]'`

**Cosmos insights empty**
→ `watcher.py` not running, or `NVIDIA_COSMOS_API_KEY` not set
→ Stub mode works without API key (realistic fake insights)

---

## Verification Checklist

- [ ] `redis-cli ping` → PONG
- [ ] Celery worker starts, logs show `simulator.tick` task registered
- [ ] Celery beat starts, logs show task scheduled every 2s
- [ ] `curl /api/tags?limit=1` → non-zero values, `node_id=sim-celery`
- [ ] PLC Reader Live Tags → values change, mode transitions in change log
- [ ] PLC Reader Trends → motor\_speed, temperature, current curves visible
- [ ] Matrix API `/api/incidents` → incidents appear during fault phases
- [ ] (If Cosmos watcher) → insights appear in `/api/insights`
- [ ] (If Discord webhooks) → #alerts gets fault embeds
