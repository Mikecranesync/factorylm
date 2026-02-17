# Super-Jarvis: The Roadmap

**Date:** 2026-02-17
**Author:** Claude (Turn 4 design)
**Canonical reference:** [FactoryLM README](https://github.com/Mikecranesync/factorylm#factorylm)

---

## Where Jarvis Is Today

After PR #4, Jarvis (OpenClaw) has 11 skills, conversation memory, Layer 0 short-circuits, and source attribution. But the architecture is still **skill-per-request** — a user texts, one skill fires, one response comes back. There's no persistent state, no proactive alerts, no learning loop, and no multi-protocol PLC support. Most of the ecosystem (70+ capabilities across 10 repos) sits on the shelf, unwired.

### Current Architecture

```
Telegram → TelegramAdapter → classify(intent) → Skill.handle() → LLM → response
                                                     ↓
                                                KB search (maybe)
                                                Matrix API (maybe)
```

**What's missing:** Everything between the user's question and the answer is ephemeral. Nothing watches. Nothing learns. Nothing acts proactively.

---

## Super-Jarvis Architecture

Super-Jarvis is not a bigger chatbot. It's a **factory nervous system** that happens to have a chat interface.

```
+==============================================================+
|                    SUPER-JARVIS                               |
+==============================================================+
|                                                              |
|  LAYER 0: THE KNOWLEDGE ENGINE                               |
|  ┌─────────────┐ ┌──────────────┐ ┌───────────────────────┐  |
|  │  Rivet KB   │ │ Logic Gates  │ │ Workflow Engine        │  |
|  │  (pgvector) │ │ (fault→fix)  │ │ (captured procedures) │  |
|  └──────┬──────┘ └──────┬───────┘ └──────────┬────────────┘  |
|         └───────────────┼────────────────────┘               |
|                         ▼                                    |
|  ┌────────────────────────────────────────────┐              |
|  │              DISPATCH CORE                 │              |
|  │  Intent Classifier → Skill Router          │              |
|  │  Conversation Memory (per-user, persistent)│              |
|  │  Observability Logger (every query traced) │              |
|  └───────┬──────────┬──────────┬──────────────┘              |
|          │          │          │                              |
|  ┌───────┴───┐ ┌────┴────┐ ┌──┴──────────┐                  |
|  │  SKILLS   │ │ WATCHERS│ │  BRAIN      │                  |
|  │  (11+)    │ │ (async) │ │ (quality +  │                  |
|  │           │ │         │ │  archiving) │                  |
|  └───────────┘ └─────────┘ └─────────────┘                  |
|                                                              |
|  ADAPTERS (dumb I/O)                                         |
|  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐              |
|  │ Tele │ │ Whts │ │Slack │ │ Web  │ │ Halo │              |
|  │ gram │ │ App  │ │      │ │  UI  │ │      │              |
|  └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘              |
|     └────────┴────────┴────────┴────────┘                    |
|                        ▼                                     |
|  DATA PLANE                                                  |
|  ┌──────────┐ ┌──────────┐ ┌──────────────┐ ┌────────────┐  |
|  │ Matrix   │ │Collectors│ │  Analytics   │ │  Cosmos    │  |
|  │ API      │ │ AB/S7/MB │ │  (drift +   │ │  (video +  │  |
|  │ (events) │ │ (polling)│ │   baseline) │ │   insight) │  |
|  └──────────┘ └──────────┘ └──────────────┘ └────────────┘  |
|                                                              |
|  LLM TIER (fallback chain)                                   |
|  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐        |
|  │ Layer 0  │→│ Layer 1  │→│ Layer 2  │→│ Layer 3  │        |
|  │ KB+code  │ │ Edge LLM │ │ Local GPU│ │ Cloud AI │        |
|  │ <100ms   │ │ 0.5-1s   │ │ 2-3s     │ │ 1-2s     │        |
|  └──────────┘ └──────────┘ └──────────┘ └──────────┘        |
+==============================================================+
```

### Three New Architectural Concepts

**1. Watchers** — Background loops that monitor data streams and create events *without* a user asking. Today Jarvis only reacts. Super-Jarvis watches.

**2. The Learning Loop** — Every query is traced. Patterns are identified. Patterns become Layer 0 code. The KB grows automatically. LLM usage decreases over time.

**3. Proactive Alerts** — When a watcher detects something (drift, fault, incident), Jarvis messages the user *first*, before they have to ask.

---

## Phase 1: Wire the Shelf (Week 1-2)

**Goal:** Connect what already works. No new code beyond glue.

### 1A. Cosmos Connector (DiagnoseSkill → CosmosAgent)

When DiagnoseSkill detects a CRITICAL or EMERGENCY fault, trigger Cosmos analysis in the background and post the insight back to the user.

```
User: "why is the motor stopped?"
Jarvis: [immediate] "🔴 M002: Motor Stopped Unexpectedly. Check motor starter..."
Jarvis: [5s later] "📊 Cosmos analysis: Root cause likely thermal overload.
         Confidence: 0.87. Similar pattern seen in incident #14."
```

**Files to modify:**
- `openclaw/skills/builtin/diagnose.py` — after fault detection, fire-and-forget `CosmosAgent.on_incident()`
- `openclaw/connectors/cosmos.py` — new connector wrapping `cosmos/client.py`
- `openclaw/app.py` — register cosmos connector

**What exists:** `cosmos/agent.py`, `cosmos/client.py` — working code, just needs HTTP wiring.

### 1B. Proactive Fault Watcher

A background task (asyncio loop, not Celery) that polls Matrix API every 30s. When `fault_alarm` flips to 1, Jarvis messages Mike *without being asked*.

```
[Jarvis → Mike, unprompted]
"⚠️ Fault detected on PLC-01:
🔴 M001: Motor Overcurrent (7.2A, limit 5.0A)
Run /diagnose for full analysis."
```

**Files to create:**
- `openclaw/watchers/fault_watcher.py` — polls Matrix `/api/tags`, runs `detect_faults()`, deduplicates, sends via adapter
- `openclaw/watchers/base.py` — base watcher class with start/stop lifecycle

**Files to modify:**
- `openclaw/app.py` — start watchers on startup, stop on shutdown

### 1C. Drift Detection Connector

Wire `analytics/drift_detector.py` behind a new OpenClaw connector. When the fault watcher sees tags, also check for drift from baseline.

```
[Jarvis → Mike, unprompted]
"📈 Drift alert: motor_current trending up.
Current: 4.8A | Baseline: 3.2A ± 0.4A (4.0σ)
Not yet a fault, but worth watching. /diagnose to investigate."
```

**Files to create:**
- `openclaw/connectors/analytics.py` — wraps `DriftDetector`, manages baselines in PostgreSQL

### 1D. Incident Timeline Skill

New skill: `/timeline` or `/incidents` — shows recent incidents, Cosmos insights, and resolution status from Matrix API.

```
User: "/incidents"
Jarvis: "Last 24h:
1. 🔴 14:32 — E001 E-stop (resolved, 12min)
2. 🟡 09:15 — T002 Elevated temp (auto-cleared)
3. 🔴 Yesterday 22:40 — M001 Overcurrent (open)
   Cosmos: 'Bearing wear pattern. Schedule PM.'"
```

**Files to create:**
- `openclaw/skills/builtin/timeline.py`
- Add `TIMELINE = "timeline"` to Intent enum

---

## Phase 2: The Learning Loop (Week 3-4)

**Goal:** Make Jarvis smarter over time without more LLM calls.

### 2A. Trace Logger (Observability)

Log every query→response pair with metadata: intent, layer used, latency, KB hit, LLM model, user feedback.

```python
@dataclass
class QueryTrace:
    timestamp: datetime
    user_id: str
    query: str
    intent: Intent
    layer_used: int          # 0, 1, 2, or 3
    kb_hit: bool
    kb_confidence: float
    llm_model: str | None
    latency_ms: int
    response_length: int
    user_feedback: str | None  # 👍/👎 reaction
```

Store in PostgreSQL (`query_traces` table). This is the raw material for the learning loop.

**Files to create:**
- `openclaw/observability/trace.py` — `QueryTrace` model + `log_trace()` function
- `openclaw/observability/metrics.py` — aggregations (queries-per-layer, avg latency, KB coverage)

**Files to modify:**
- Every skill's `handle()` — wrap with trace logging (decorator or base class method)

### 2B. Pattern Extractor (Traces → Layer 0)

Weekly batch job: scan query traces, find repeated LLM-answered questions (same intent, similar embedding), and promote them to KB atoms.

```
Day 1:  "how do I reset the e-stop?" → Layer 3 (Claude) → answer
Day 5:  "reset e-stop procedure" → Layer 3 (Groq) → similar answer
Day 10: "e-stop reset steps" → Layer 3 (Groq) → similar answer
Day 11: [Pattern detected] → Create KB atom "E-Stop Reset Procedure"
Day 12: "how to reset e-stop?" → Layer 0 (KB direct, 0ms) ✅
```

**Files to create:**
- `openclaw/observability/pattern_extractor.py` — embeddings-based clustering of traces, auto-creates KB atoms via knowledge connector

This is the core of "intelligence flows downward." Every repeated question becomes a Layer 0 answer.

### 2C. Hammurabi Quality Gate

Before any LLM response reaches the user, pass it through Hammurabi for quality scoring. If score < threshold, retry with a different provider or flag for review.

**Files to create:**
- `openclaw/quality/gate.py` — wraps `brain/hammurabi.py` heuristics
- Hook into `LLMRouter.route()` as post-processing step

### 2D. Herodotus Knowledge Archiver

After every meaningful interaction (diagnosis, incident, resolution), Herodotus extracts entities and archives them to the KB. The KB grows from every conversation.

```
User: "the motor overheated because the cooling fan belt broke"
Herodotus: [extracts] {
  entity: "cooling fan belt failure",
  type: "root_cause",
  linked_fault: "T001",
  resolution: "replace cooling fan belt",
  source: "technician_report"
}
→ New KB atom created
→ Next time T001 fires, Layer 0 returns "Check cooling fan belt"
```

---

## Phase 3: Multi-Adapter + Edge (Week 5-8)

**Goal:** Jarvis works on WhatsApp (primary market), and can run air-gapped.

### 3A. WhatsApp Adapter

The vision says WhatsApp is PRIMARY. Telegram is for power users. The adapter is dumb — same `InboundMessage` → dispatch → `OutboundMessage` pattern.

```
openclaw/gateway/whatsapp.py
```

Use the WhatsApp Business API (Cloud API). Same skill dispatch, same KB, same Layer 0. Only I/O changes.

**Key difference:** WhatsApp users are factory technicians in Latin America. Default language: Spanish. Phone number detection (+58 = Venezuela, +52 = Mexico, etc.) sets locale.

### 3B. Web Dashboard

Admin-facing web UI showing:
- Live PLC tag status (real-time via WebSocket)
- Incident timeline with Cosmos insights
- Query trace analytics (queries-per-layer chart, Layer 0 coverage growth)
- KB health (atom count, coverage gaps, staleness)

```
openclaw/gateway/web.py        # FastAPI + Jinja2 or separate React app
```

### 3C. Edge Deployment (Raspberry Pi)

Package Layer 0 + Layer 1 for Raspberry Pi 4:
- Vector DB (sqlite-vss or hnswlib, not pgvector)
- Edge LLM (Qwen 0.5B via llama.cpp)
- Fault detection rules (pure Python, no dependencies)
- Modbus collector (direct serial/TCP)
- Local API server (uvicorn)

No internet required. Layer 2 and 3 disabled. This is **Deployment Scenario D** from the vision.

```
factorylm-edge/
├── kb/            # Pre-built vector index
├── models/        # Quantized Qwen 0.5B
├── rules/         # Fault detection Python
├── collector/     # Modbus RTU reader
├── server.py      # FastAPI on port 8340
└── install.sh     # Single-command setup
```

### 3D. Halo Glasses Integration

Voice-first interface for hands-free factory floor use:
- STT (Whisper on-device or via Groq)
- Intent classification
- TTS response (already have edge-tts)
- No screen interaction needed

This is the vision's "Halo Glasses" adapter — same dumb adapter pattern.

---

## Phase 4: Autonomous Operations (Week 9-12)

**Goal:** Jarvis runs the factory floor with minimal human input.

### 4A. Shift Briefing

Every shift start (6 AM, 2 PM, 10 PM), Jarvis sends a summary:

```
[Jarvis → Shift Lead, 6:00 AM]
"🏭 Shift Briefing — Feb 18, Day Shift

Equipment Status:
✅ Line 1: Running normal (4h uptime)
🟡 Line 2: Elevated temp (T002, 72°C, trending up)
⛔ Line 3: Down since 02:15 (M001, motor overcurrent)

Open Work Orders: 3
  - WO-0047: Replace Line 3 motor bearings (scheduled today)
  - WO-0045: Calibrate pressure sensor Bay 4
  - WO-0043: PM on compressor #2

KB Coverage: 78% of queries answered by Layer 0 (up from 64% last week)

Priority: Line 3 motor. Parts are in stock. See /diagnose for details."
```

### 4B. Predictive Maintenance

Combine drift detection + baseline analytics + historical incidents to predict failures before they happen.

```
[Jarvis → Mike, proactive]
"📊 Predictive alert: Line 2 motor current has drifted 2.1σ
above baseline over the past 72 hours.

Historical pattern match: This pattern preceded M001 (overcurrent)
in 3 of 4 similar cases, with average 5 days to failure.

Recommendation: Schedule bearing inspection within 3 days.
Create work order? /wo Line 2 motor bearing inspection"
```

### 4C. Multi-PLC Orchestration

Wire all three collector types (Modbus, S7, AB) through a unified tag engine. Jarvis monitors multiple PLCs simultaneously.

```
[Jarvis knows about all PLCs]
User: "what's happening on the floor?"
Jarvis: "3 PLCs online:
  PLC-01 (AB Micro820): Running, all normal
  PLC-02 (Siemens S7-1200): Line 2, elevated temp warning
  PLC-03 (Modbus RTU): Offline since 04:30 (check connection)"
```

### 4D. Action Approval Queue

For actions that require human approval (the read-only constraint), Jarvis proposes and queues:

```
[Jarvis → Mike]
"🔧 Recommended action: Reduce Line 2 motor speed to 70%
to prevent thermal trip.

This requires writing to PLC-02 register 40001.
Approve? Reply /approve or /deny"

[Mike → Jarvis]
"/approve"

[Jarvis → PLC Operator]
"✅ Mike approved speed reduction. Please set Line 2 motor
speed to 70% manually via HMI."
```

Note: Jarvis never writes to PLCs. It tells a human what to do and confirms they did it. Read-only constraint preserved.

---

## The Metrics That Matter

These numbers tell you if super-Jarvis is working:

| Metric | Today | Phase 1 | Phase 2 | Phase 4 |
|--------|-------|---------|---------|---------|
| Layer 0 query % | ~5% | ~15% | ~40% | ~75% |
| Avg response time | 2-4s | 1-3s | 0.5-2s | <500ms |
| Cost per query | $0.01-0.05 | $0.005-0.03 | $0.002-0.01 | ~$0.001 |
| KB atoms | ~50 | ~100 | ~500 | ~2000+ |
| Proactive alerts | 0/day | 2-5/day | 5-10/day | 10-20/day |
| Adapters | 1 (Telegram) | 1 | 2 (+ WhatsApp) | 4+ |
| PLCs monitored | 1 | 1 | 2-3 | unlimited |
| Faults auto-diagnosed | 8 codes | 8 + Cosmos | 20+ | 50+ |
| Mean time to notify | ∞ (reactive) | <30s | <15s | <5s |

The north star: **Layer 0 query percentage goes up every week.** If it's not going up, the learning loop is broken.

---

## What NOT to Build

Equally important — things that violate the vision:

1. **PLC write capability** — Never. Read-only is a feature, not a limitation. It eliminates fear, simplifies IT approval, removes liability.

2. **Monolithic LLM dependency** — No skill should *require* an LLM. Every skill must have a Layer 0 fallback path, even if it's just "I don't have an answer for this yet."

3. **Smart adapters** — Adapters stay dumb. No business logic in WhatsApp/Telegram/Slack handlers. All intelligence in the core.

4. **Custom ML models** — Don't train custom models when rule-based fault detection + KB search works. ML is Layer 2-3. Rules are Layer 0.

5. **Real-time control loops** — Jarvis is diagnostic, not a SCADA replacement. Sub-second polling for monitoring is fine. Closed-loop control is out of scope.

---

## Implementation Priority (If Starting Tomorrow)

If I had to pick the single highest-ROI item from each phase:

| Phase | Item | Why | Effort |
|-------|------|-----|--------|
| 1 | **Proactive Fault Watcher** (1B) | Transforms Jarvis from reactive chatbot to proactive monitor. Massive perceived value. | 4-6 hours |
| 2 | **Trace Logger** (2A) | Without traces, there's no learning loop. Every other Phase 2 item depends on this. | 3-4 hours |
| 3 | **WhatsApp Adapter** (3A) | Primary market is LatAm. Telegram is dev-only. WhatsApp is where the customers are. | 1-2 days |
| 4 | **Shift Briefing** (4A) | Zero-effort daily value. Proves Jarvis is watching even when nobody asks. | 4-6 hours |

---

## Relationship to Existing Repos

| Repo | Role in Super-Jarvis |
|------|---------------------|
| `openclaw` | The brain — skills, routing, adapters, watchers |
| `factorylm` (monorepo) | The body — collectors, analytics, cosmos, workers, matrix API |
| `factorylm-core` | The nervous system — unified LLM client for all tiers |
| `factorylm-plc-client` | The hands — mature Modbus library for PLC reads |
| `voltron` | The skeleton — distributed architecture for multi-site |
| `remoteme-jarvis-node` | The eyes — remote shell, screenshots, file ops on each machine |
| `jarvis-workspace` | The memory — SOUL.md identity, persistent context |

Super-Jarvis doesn't replace any of these. It wires them together through OpenClaw's skill/connector/watcher architecture.

---

## Decision Points for Mike

Before implementation, these choices shape the architecture:

1. **Persistence for conversation memory** — Currently in-memory (lost on restart). Move to PostgreSQL (Rivet DB) or Redis? Redis is faster but another dependency. PostgreSQL is already there.

2. **Watcher polling vs. webhook** — Poll Matrix API every 30s, or have Matrix push events to OpenClaw? Polling is simpler. Webhooks are faster.

3. **WhatsApp provider** — Cloud API (Meta-hosted, easy) or On-Premise API (self-hosted, GDPR-friendly for enterprise)? Cloud API is the right v1.

4. **Edge hardware** — Raspberry Pi 4 or Pi 5? Pi 5 can run Qwen 2.5-1.5B which is significantly better than 0.5B. Cost difference is ~$25.

5. **Trace storage** — Same PostgreSQL as KB, or separate analytics DB? Same DB is simpler. Separate scales better.

---

*This document is the Turn 4 output. It is a proposal, not a commitment. Mike approves what ships.*
