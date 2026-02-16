# WF-008: Cosmos R2 Demo Prep (10-Day Sprint)

| Field | Value |
|-------|-------|
| **ID** | WF-008 |
| **Created** | 2026-02-16 |
| **Last Verified** | 2026-02-16 |
| **Status** | verified (Day 1 pipeline validated 2026-02-16) |
| **Services** | matrix-api, cosmos-agent, cosmos-watcher, factoryio-bridge |
| **Devices** | travel-laptop, plc-laptop |
| **Est. Duration** | 10 days (Feb 16–25) |

---

## Purpose

Prepare the FactoryLM × NVIDIA Cosmos Reason 2 submission for the Cosmos Cookoff competition (deadline Feb 26, 2026 @ 5:00 PM PT). This workflow tracks the daily checklist from pipeline validation through to final submission.

## Prerequisites

- [ ] All competition code exists in `factorylm-monorepo` (cosmos/, services/matrix/, sim/, diagnosis/)
- [ ] Docker installed (for Postgres, optional — SQLite works as fallback)
- [ ] Python 3.11+ with `uvicorn`, `fastapi`, `httpx`, `pyyaml` installed
- [ ] OBS or screen recording tool available for demo video
- [ ] Access to build.nvidia.com for API key application

## Steps

### Day 1 (Feb 16): Validate Pipeline

- **Device**: travel-laptop
- **Goal**: Prove end-to-end stub demo works

#### 1.1 Start Docker Postgres (optional)

```bash
cd infra/local && docker-compose up -d
```
- **Expected Output**: `factorylm-postgres` container running on :5432
- **Verify**: `docker ps | grep factorylm-postgres`
- **Note**: Matrix API defaults to SQLite — Postgres is optional

#### 1.2 Start Matrix API

```bash
python -m uvicorn services.matrix.app:app --host 0.0.0.0 --port 8000
```
- **Expected Output**: `Uvicorn running on http://0.0.0.0:8000`
- **Verify**: `curl http://localhost:8000/api/health`

#### 1.3 Start Factory I/O Bridge (Simulator Mode)

```bash
python sim/factoryio_bridge.py --sim --interval 500
```
- **Expected Output**: Tag snapshots posting to Matrix API every 500ms
- **Verify**: `curl http://localhost:8000/api/tags` returns recent snapshots

#### 1.4 Start Cosmos Watcher

```bash
python -m cosmos.watcher --matrix-url http://localhost:8000 --interval 5
```
- **Expected Output**: Polling for incidents every 5s
- **Verify**: Watcher logs show "Checking for incidents..."

#### 1.5 Inject Fault and Verify Insight

```bash
TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ) && \
curl -X POST http://localhost:8000/api/tags \
  -H "Content-Type: application/json" \
  -d "{\"node_id\": \"plc-sim-001\", \"timestamp\": \"$TIMESTAMP\", \"motor_running\": true, \"motor_speed\": 1500, \"motor_current\": 7.2, \"temperature\": 45.0, \"pressure\": 85, \"conveyor_running\": false, \"conveyor_speed\": 0, \"sensor_1\": true, \"sensor_2\": true, \"fault_alarm\": true, \"e_stop\": false, \"error_code\": 3, \"error_message\": \"Conveyor jam detected\"}"
```
- **Expected Output**: Incident created, watcher picks it up, insight generated
- **Verify**: `curl http://localhost:8000/api/insights` returns at least one insight

#### 1.6 Run Loop Test

```bash
python cosmos/loop_test.py
```
- **Expected Output**: Full closed-loop test passes
- **Verify**: AI diagnosis matches injected fault state

#### 1.7 Apply for Cosmos API Key

- Go to build.nvidia.com and request access to Cosmos Reason 2
- Post in Cosmos Cookoff Discord #questions for fastest access
- **This is a manual step for Mike**

**Day 1 Deliverable**: End-to-end stub demo running. API key application submitted.

---

### Day 2 (Feb 17): End-to-End Polish

- **Device**: travel-laptop
- **Goal**: Test all fault types, fix issues from Day 1

#### 2.1 Fix Day 1 Issues

Address any failures from pipeline validation.

#### 2.2 Test All 6 Fault Types

Inject each fault type and verify stub response:

| error_code | Fault | Curl field overrides |
|------------|-------|---------------------|
| 0 | Normal (clear) | `fault_alarm: false, error_code: 0` |
| 1 | Motor overload | `motor_current: 7.2, error_code: 1` |
| 2 | Overheat | `temperature: 92.0, error_code: 2` |
| 3 | Conveyor jam | `sensor_1: true, sensor_2: true, error_code: 3` |
| 4 | Sensor failure | `error_code: 4` |
| 5 | Comms loss | `error_code: 5` |

#### 2.3 Verify Incident Detail Endpoint

```bash
curl http://localhost:8000/api/incidents/1
```
- **Expected Output**: Incident JSON with nested `cosmos_insight` object

#### 2.4 Check for API Key

If key arrived, proceed to Day 4 tasks (swap stub for real API).

**Day 2 Deliverable**: All 6 fault types tested. Pipeline stable.

---

### Day 3 (Feb 18): HMI + Jarvis Integration

- **Device**: travel-laptop + vps
- **Goal**: Incident detail view + Jarvis diagnose skill wired to Cosmos

#### 3.1 Build Incident Detail View

Enhance Matrix API web HMI (`/` route in `services/matrix/app.py`) to show:
- Tag history for incident
- CosmosInsight panel (summary, root cause, confidence, suggested checks)

#### 3.2 Wire Jarvis Diagnose Skill

On VPS, update OpenClaw `diagnose` skill to fetch latest CosmosInsight from Matrix API:
```
GET http://<travel-laptop>:8000/api/insights?limit=1
```

#### 3.3 Test End-to-End with Jarvis

- Inject fault → watcher generates insight → Jarvis reports via Telegram

**Day 3 Deliverable**: HMI shows insights. Jarvis reports faults.

---

### Day 4 (Feb 19): Real Cosmos API

- **Device**: travel-laptop
- **Goal**: Swap stub for real API, tune prompts

#### 4.1 Swap Stub for Real API

Set `NVIDIA_COSMOS_API_KEY` environment variable. The `cosmos/client.py` automatically uses real API when key is present.

```bash
export NVIDIA_COSMOS_API_KEY="your-key-here"
```

#### 4.2 Test 3 Fault Types with Real Cosmos

Run pipeline with real API for: jam (3), overload (1), overheat (2).

#### 4.3 Tune Prompts

Compare real vs stub responses. Adjust prompts in `cosmos/client.py` if needed.

#### 4.4 Fallback Plan

If no API key by end of Day 5, submit with Llama 70B fallback (already in `cosmos/client.py`). Document both paths in README.

**Day 4 Deliverable**: Real Cosmos (or Llama fallback) producing quality insights.

---

### Day 5 (Feb 20): Demo Script + Recording Prep

- **Device**: travel-laptop
- **Goal**: Demo script written, first recording attempt

#### 5.1 Write Demo Script

- Narration: FactoryLM pitch → fault injection → Cosmos insight → operator view
- Target: 2-4 minutes
- Fault sequence: normal → jam → Cosmos diagnosis → operator sees insight

#### 5.2 Practice Demo Flow (3x)

Note timing, identify hiccups, smooth transitions.

#### 5.3 Record First Take

Screen recording with OBS or similar. Capture all 3 terminals + web HMI.

**Day 5 Deliverable**: Demo script finalized. First video draft recorded.

---

### Day 6-7 (Feb 21-22): Polish + Multiple Scenarios

- **Device**: travel-laptop + plc-laptop (optional)
- **Goal**: Final video, multiple fault scenarios

#### 6.1 Record Final Demo Video (2-4 min)

#### 6.2 Test with Factory I/O (if PLC laptop available)

```bash
python sim/factoryio_bridge.py --plc-host 100.72.2.99 --interval 1000
```

#### 6.3 Add Second Fault Scenario

E.g., overheat following jam to show cascade diagnosis.

#### 6.4 Polish HMI

Make incident detail view presentable for judges.

**Day 6-7 Deliverable**: Final demo video. HMI polished.

---

### Day 8-9 (Feb 23-24): README + Submission Repo

- **Device**: travel-laptop
- **Goal**: Judge-ready README, public submission repo

#### 8.1 Write Judge-Ready README

Include: architecture diagram, setup in <5 min, demo flow, what Cosmos does, safety constraints.

#### 8.2 Create Public Submission Repo

Clean copy of competition-relevant code only. No secrets, no internal docs.

#### 8.3 Architecture Diagram

Mermaid or ASCII diagram for README.

#### 8.4 Final End-to-End Test from Clean Clone

Clone submission repo fresh, follow README setup, verify it works.

**Day 8-9 Deliverable**: Public repo ready. README reviewed.

---

### Day 10 (Feb 25): Final Check + Submit

- **Device**: travel-laptop
- **Goal**: Submit before deadline

#### 10.1 Run Full Demo One More Time

#### 10.2 Proofread README

#### 10.3 Submit

Submit before 5:00 PM PT on Feb 26.

**Day 10 Deliverable**: Submission complete.

---

## Verification

End-to-end confirmation that the full demo works:

```bash
# Terminal 1
python -m uvicorn services.matrix.app:app --host 0.0.0.0 --port 8000

# Terminal 2
python sim/factoryio_bridge.py --sim --interval 500

# Terminal 3
python -m cosmos.watcher --matrix-url http://localhost:8000 --interval 5

# Inject fault (timestamp is required)
TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ) && \
curl -X POST http://localhost:8000/api/tags \
  -H "Content-Type: application/json" \
  -d "{\"node_id\":\"test\",\"timestamp\":\"$TIMESTAMP\",\"motor_running\":true,\"motor_speed\":1500,\"motor_current\":7.2,\"temperature\":45,\"pressure\":85,\"conveyor_running\":false,\"conveyor_speed\":0,\"sensor_1\":true,\"sensor_2\":true,\"fault_alarm\":true,\"e_stop\":false,\"error_code\":3,\"error_message\":\"Conveyor jam\"}"

# Wait 10s for watcher to pick it up, then:
curl http://localhost:8000/api/insights
# Should return insight with summary, root_cause, confidence, suggested_checks
```

## Rollback

No system changes to roll back — this is a competition sprint on local dev machines.

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Matrix API won't start | Port 8000 in use | `lsof -i :8000` and kill the process, or use `--port 8001` |
| Bridge can't connect to Matrix | Matrix API not running | Start Matrix API first |
| Watcher sees no incidents | No fault_alarm=true tags posted | Inject a fault manually with curl |
| Insight is stub, not real Cosmos | `NVIDIA_COSMOS_API_KEY` not set | Export the key or use Llama fallback |
| Docker Postgres won't start | Docker not running on WSL | `sudo service docker start` or skip Postgres (SQLite works) |
| loop_test.py fails | Matrix API URL mismatch | Check `--matrix-url` argument matches actual Matrix API host:port |

## Decomposition

| Task | Can Automate | Notes |
|------|-------------|-------|
| Start Matrix API | yes | uvicorn command |
| Start bridge (sim) | yes | python command with --sim flag |
| Start watcher | yes | python command |
| Inject test faults | yes | curl POST commands |
| Verify insights | yes | curl GET + JSON parse |
| Record demo video | no | Requires human narration and screen capture |
| Write README | no | Requires human judgment on presentation |
| Apply for API key | no | Manual registration on build.nvidia.com |

## History

| Date | Change | Trace |
|------|--------|-------|
| 2026-02-16 | Initial creation — 10-day sprint plan for Cosmos Cookoff | TRC-2026-02-16-004 |
