# 🏭 Cosmos Factory — FactoryLM × NVIDIA Cosmos Cookoff 2026

*"Who'll stop the rain on the factory floor? Cosmos will."*  
— Named after Creedence Clearwater Revival's *Cosmo's Factory* (1970)

**Deadline:** Feb 26, 2026 5 PM PT  
**Status:** ACTIVE — Fine-tuning Cosmos Reason 2-2B on factory fault video  
**Budget:** ~$67 GPU rental  
**Last Updated:** 2026-02-17

---

## 🎯 The Pitch (30 seconds)

FactoryLM fine-tunes **NVIDIA Cosmos Reason 2** on factory floor video to diagnose equipment faults — conveyor jams, motor overloads, sensor failures — from video + PLC sensor data. The fine-tuned model runs **locally, air-gapped**, on a Layer 2 GPU server. No cloud required. Successful diagnoses flow downward into deterministic Layer 0 code, requiring *less* AI over time.

**Pipeline:** `Factory I/O Simulation → Modbus TCP → Matrix API → Fine-Tuned Cosmos Reason 2 → Root-Cause Diagnosis`

---

## 🧠 Why Fine-Tuning Wins

| Approach | What judges see | Strength |
|----------|----------------|----------|
| ❌ Cloud API call | "We called an endpoint" | Generic, anyone can do it |
| ❌ Base model inference | "We ran the model" | Better, but still generic |
| ✅ **Fine-tuned on our data** | "We adapted Cosmos to our equipment, it runs locally" | **Domain expertise + NVIDIA cookbook + air-gapped deployment** |

NVIDIA's own [Cosmos Cookbook](https://nvidia-cosmos.github.io/cosmos-cookbook/) shows Uber fine-tuning Cosmos Reason 2 for autonomous vehicle video. **We're doing the same thing for industrial equipment.** Same cookbook, different domain.

---

## 📐 Architecture — 4-Layer Intelligence Stack

```
┌─────────────────────────────────────────────────────────────────┐
│  LAYER 0: Deterministic Code + Knowledge Base                   │
│  ├── Vector DB (equipment manuals, fault patterns)              │
│  ├── Logic gates (pattern-matched from AI observations)         │
│  └── Response: <100ms | Cost: $0                                │
│         ▲ Intelligence flows DOWN — AI learnings become code    │
├─────────────────────────────────────────────────────────────────┤
│  LAYER 1: Edge LLM (Raspberry Pi)                               │
│  ├── Qwen 0.5B, Llama 1B — simple command parsing              │
│  └── Response: 0.5-1s | Cost: $0 | ON-DEVICE                   │
├─────────────────────────────────────────────────────────────────┤
│  LAYER 2: Local GPU Server ← COSMOS REASON 2 LIVES HERE        │
│  ├── Fine-tuned Cosmos Reason 2-2B (factory fault diagnosis)    │
│  ├── Video + PLC tags → structured root-cause analysis          │
│  └── Response: 2-3s | Cost: electricity | AIR-GAPPED            │
├─────────────────────────────────────────────────────────────────┤
│  LAYER 3: Cloud AI (optional, last resort)                      │
│  ├── Llama 3.1 70B via NVIDIA API (fallback)                    │
│  └── Response: 1-2s | Cost: $0.01-0.10 | OPTIONAL               │
└─────────────────────────────────────────────────────────────────┘
```

**Key principle:** Intelligence flows **downward**. Every successful Cosmos diagnosis gets traced, logged, and eventually encoded as a Layer 0 deterministic rule. The goal is to need *less* AI over time.

---

## 🔧 End-to-End Data Flow

```
Factory I/O (Conveyor Sim)
        │ Modbus TCP (coils + registers at 2 Hz)
        ▼
  factoryio_bridge.py
        │ HTTP POST /api/tags
        ▼
  Matrix API (FastAPI + SQLite)
        │ Auto-creates incidents on fault_alarm=true
        ▼
  Cosmos Watcher (cosmos/watcher.py)
        │ Polls /api/incidents?status=open
        │ Bundles: video clip + PLC tags + context
        │ Sends to fine-tuned Cosmos Reason 2-2B
        ▼
  Fine-Tuned Cosmos Reason 2-2B (Layer 2 GPU)
        │ Returns structured JSON:
        │   { summary, root_cause, confidence,
        │     reasoning, suggested_checks }
        ▼
  Matrix API → Web HMI Dashboard
        │ Operator sees diagnosis in browser
        │ Pattern logged → feeds Layer 0
        ▼
  Technician acts on diagnosis
```

---

## 📊 Fine-Tuning Plan

### Model Choice

| Model | Params | VRAM (inference) | VRAM (training) | Why |
|-------|--------|-----------------|-----------------|-----|
| Cosmos Reason 2-8B | 8B | 56GB+ | 80GB+ multi-GPU | Too expensive, overkill |
| **Cosmos Reason 2-2B** ⭐ | 2.4B | 24GB | ~40-50GB (1× A100) | **Fits edge story, cheaper, faster training** |

**Base architecture:** Qwen3-VL-2B-Instruct (post-trained by NVIDIA with physical reasoning data)

### Training Data: 5 Fault Types + Normal Operation

| Fault | error_code | Video Source | Training Clips |
|-------|------------|-------------|----------------|
| Normal operation | 0 | Factory I/O conveyor running | 20 clips |
| Motor overload | 1 | High current, motor struggling | 20 clips |
| Temperature high | 2 | Gradual thermal rise | 20 clips |
| **Conveyor jam** | **3** | **Parts stuck, belt stopped** | **30 clips** (most common) |
| Sensor failure | 4 | Erratic/flatline readings | 20 clips |
| E-Stop | 5 | Emergency stop pressed | 15 clips |
| **Total** | | | **~125 clips** |

> **Demo scenario note:** The conveyor jam / motor paradox condition (`error_code=3`, motor energized + belt speed zero) is currently a **hardcoded stub response** in `cosmos/client.py` — it is not detected by live PLC register correlation. The fine-tuning plan above is the path to replacing this stub with a model that identifies the pattern from video and sensor data in real time.

Each clip is 10-30 seconds of Factory I/O screen capture paired with:
- PLC tag snapshot (motor_current, temperature, conveyor_speed, error_code, etc.)
- Expected diagnosis (summary, root_cause, confidence, suggested_checks)

### Training Format

Following the [NVIDIA Cosmos Cookbook post-training recipe](https://nvidia-cosmos.github.io/cosmos-cookbook/recipes/post_training/reason2/video_caption_vqa/post_training.html):

```json
{
  "video": "clips/jam_003.mp4",
  "prompt": "Analyze this factory floor video along with the PLC sensor data. Equipment Node: factoryio-sim. Current Tags: {motor_running: true, motor_current: 8.5, conveyor_speed: 0, fault_alarm: true, error_code: 3}. Provide: summary, root_cause, confidence, reasoning, suggested_checks.",
  "response": "{\"summary\": \"Conveyor jam detected...\", \"root_cause\": \"Physical obstruction in conveyor path\", \"confidence\": 0.88, ...}"
}
```

### GPU & Cost

| Item | Spec | Hours | Cost |
|------|------|-------|------|
| Training GPU | RunPod A100 80GB SXM | 15-20 hrs | $41-54 |
| Inference testing | RunPod A100 80GB SXM | 5-8 hrs | $14-22 |
| Storage | 30GB disk, 9 days | — | $2 |
| **Total** | | **20-28 hrs** | **$57-78** |

---

## 📅 9-Day Sprint

| Day | Date | Task | GPU? | Deliverable |
|-----|------|------|------|-------------|
| **1** | Feb 17 (Mon) | Spin up RunPod A100. Install cosmos-reason2 repo. Test base model inference | ✅ 3 hrs | Base model running, verified |
| **2** | Feb 18 (Tue) | Record Factory I/O fault videos. Screen capture each fault type, 20-30 clips each | ❌ Local | 125 video clips in `data/training/` |
| **3** | Feb 19 (Wed) | Build training dataset: pair videos with PLC tags + expected diagnoses. Write dataloader | ✅ 2 hrs | Training JSONL + dataloader script |
| **4** | Feb 20 (Thu) | **SFT Run 1**: Fine-tune Cosmos Reason 2-2B using cosmos-rl cookbook. ~250-500 steps | ✅ 8 hrs | First checkpoint |
| **5** | Feb 21 (Fri) | Evaluate checkpoint on held-out clips. Compare vs base model. Adjust if needed | ✅ 4 hrs | Evaluation metrics, go/no-go |
| **6** | Feb 22 (Sat) | Deploy fine-tuned model. Update `cosmos/client.py` to point at RunPod endpoint. End-to-end test | ✅ 3 hrs | Full pipeline working with fine-tuned model |
| **7** | Feb 23 (Sun) | Record demo video: Factory I/O fault → Cosmos diagnosis → dashboard | ✅ 2 hrs | Raw demo footage |
| **8** | Feb 24 (Mon) | Edit demo video (2-4 min). Polish COOKOFF_README.md for judges | ❌ Local | Demo video + README |
| **9** | Feb 25 (Tue) | Final repo cleanup. Submit before 5 PM PT Feb 26 | ❌ Local | **Submission complete** |

### Fallback Plan

If fine-tuning doesn't converge by Day 5:
- **Fall back to base model inference** (still a strong entry)
- Use the fine-tuning *attempt* as part of the story: "Here's our pipeline, here's our training data, here's what we learned"
- Llama 3.1 70B fallback via cloud API is already working

---

## ✅ What's Already Built

| Component | Status | File |
|-----------|--------|------|
| Matrix API (tag ingestion, incidents, insights, web HMI) | ✅ Working | `services/matrix/app.py` |
| Cosmos client (real API + Llama fallback + stubs) | ✅ Working | `cosmos/client.py` |
| Cosmos watcher (polls incidents, calls Cosmos) | ✅ Working | `cosmos/watcher.py` |
| Factory I/O bridge (Modbus + simulator) | ✅ Working | `sim/factoryio_bridge.py` |
| PLC simulator (5 fault types, interactive injection) | ✅ Working | `sim/plc_simulator.py` |
| End-to-end smoke test (6/6 steps pass in 2.4s) | ✅ Working | `scripts/smoke_test.py` |
| Discord adapter bot | ✅ Built | `services/discord-adapter/bot.py` |
| Network architecture diagrams | ✅ Published | [Gist](https://gist.github.com/Mikecranesync/e8f95da626fd0b4adcb8df13bb62ba96) |
| Cosmos agent (SQLite incident watcher) | ✅ Working | `cosmos/agent.py` |
| Web HMI dashboard (live tags + incidents + Cosmos insights) | ✅ Working | `services/matrix/app.py` (inline HTML) |
| Video diary pipeline | ✅ Exists | `video/*.py` |

## 🔲 What Still Needs Doing

| Task | Owner | Day |
|------|-------|-----|
| Spin up RunPod A100 | Mike (manual) | 1 |
| Record 125 Factory I/O fault videos | Mike (manual) | 2 |
| Build training data pipeline | Automated | 3 |
| Fine-tune Cosmos Reason 2-2B | Automated | 4-5 |
| Deploy + integrate fine-tuned model | Automated | 6 |
| Record demo video | Mike (manual) | 7-8 |
| Submit | Mike (manual) | 9 |

---

## 🔑 Human Actions (Mike Only)

### Action 1: Spin Up RunPod A100 (Today)
1. Go to [runpod.io](https://runpod.io), create account
2. Add $75 credit (covers full 9 days)
3. Deploy **GPU Pod** → **A100 SXM 80GB** → **PyTorch** template → 50GB disk
4. SSH in, clone cosmos-reason2 repo, verify GPU works

### Action 2: Get NGC API Key
1. Go to [org.ngc.nvidia.com/setup/api-keys](https://org.ngc.nvidia.com/setup/api-keys)
2. Generate Personal API Key (select NGC Catalog)
3. Use this to pull the NIM container: `docker login nvcr.io`

### Action 3: Record Factory I/O Videos (Day 2)
1. Open Factory I/O on PLC laptop
2. Load "Sorting by Height" scene
3. Screen record (OBS or Windows Game Bar) while triggering each fault type
4. Save as MP4 (H264 codec), 10-30 seconds each
5. Transfer to RunPod instance

### Action 4: Register Discord Bot (When Ready)
- See `COOKOFF_HUMAN_ACTIONS.md` Action 2

### Action 5: Post in Cookoff Discord
```
🏭 Hey everyone — Mike from FactoryLM here.

Building "Cosmos Factory" — an industrial AI platform that fine-tunes Cosmos 
Reason 2-2B on factory floor video to diagnose equipment faults. Connected to 
real PLCs (Allen-Bradley Micro 820) via Modbus TCP.

Pipeline: Factory I/O simulation + PLC tags + video → fine-tuned Cosmos Reason 2 
→ structured root-cause analysis → operator dashboard.

Fine-tuning using the Cosmos Cookbook post-training recipe (the Uber/AV example 
adapted for industrial equipment). Model deploys locally, air-gapped.

GitHub: https://github.com/Mikecranesync/factorylm
Architecture: https://gist.github.com/Mikecranesync/e8f95da626fd0b4adcb8df13bb62ba96
```

---

## 📁 Key Files

| File | Purpose |
|------|---------|
| `services/matrix/app.py` | Matrix API — tags, incidents, insights, web HMI |
| `cosmos/client.py` | Cosmos API client (will point at fine-tuned model) |
| `cosmos/watcher.py` | Incident watcher → Cosmos analysis loop |
| `cosmos/agent.py` | Async agent for SQLite-based watching |
| `cosmos/models.py` | CosmosInsight dataclass |
| `sim/factoryio_bridge.py` | PLC/simulator → Matrix bridge |
| `sim/plc_simulator.py` | Realistic PLC simulator with fault injection |
| `services/discord-adapter/bot.py` | Discord community bot |
| `scripts/smoke_test.py` | End-to-end pipeline verification (6/6 pass) |
| `config/factoryio.yaml` | Modbus address mapping |
| `COSMOS_FACTORY.md` | This file — the master plan |

---

## 🌐 Network Map

| Machine | IP | Role |
|---------|-----|------|
| PLC Laptop | 100.72.2.99 (Tailscale) | Factory I/O + PLC API |
| Travel Laptop | local | Coordinator, dev, Matrix API |
| RunPod A100 | (dynamic) | Cosmos Reason 2 training + inference |
| ultron (DO) | 100.68.120.99 (Tailscale) | OpenClaw bot |
| hetzner | 46.225.103.156 | Reverse proxy (pending) |

---

## 🎵 Why "Cosmos Factory"

Creedence Clearwater Revival's *Cosmo's Factory* (1970) was named after the band's rehearsal space — a warehouse where they worked relentlessly, turning raw material into hits. That's what we're doing: taking raw factory data and turning it into intelligence.

Also: **Cosmos** (the model) + **Factory** (the domain) = **Cosmos Factory**. It just works.

---

## 📊 Competition Differentiators

1. **Real hardware integration** — Modbus TCP to Allen-Bradley PLC, not just simulated data
2. **Fine-tuned Cosmos** — Domain-adapted using NVIDIA's own cookbook, not generic inference
3. **4-layer intelligence stack** — AI gets LESS important over time (unique philosophy)
4. **Air-gapped capable** — Model runs locally, no cloud dependency
5. **Read-only safety** — System never writes to PLCs
6. **End-to-end pipeline** — Video + PLC tags → diagnosis → operator dashboard
7. **Open source** — Full codebase on GitHub

---

*Cosmos Factory. Intelligence flows down. Who'll stop the rain? We will.*
