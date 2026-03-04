# FactoryLM Architecture Plan
# System Integration Map and Production Roadmap

**Author:** Atlas (Principal Architect)
**Date:** 2026-03-04
**Status:** CANONICAL — Use this for all engineering prioritization decisions
**Based on:** Full codebase analysis of the factorylm monorepo as of commit 3fd5a86

---

## Executive Summary

FactoryLM is a tiered industrial AI platform with a working foundation and significant untapped integration surface. The core data flow — phone message reaches Telegram, bot asks PLC what is happening, LLM interprets the answer, response goes back to phone — is architecturally sound and most of the necessary code exists. The main blocker is **missing glue**: services that exist independently are not wired together into a running system.

This document maps what is built, what is wired, what is stubbed, and what is missing entirely, then provides a prioritized roadmap to get the full demo loop production-ready and the intelligence-downward principle concretely implemented.

---

## Part 1: The Integration Map — What Connects to What

### The Actual Data Flow (Phone to Response)

```
PHONE (Mike)
    |
    | Telegram message: "Why is the conveyor stopped?"
    v
TELEGRAM API (cloud)
    |
    | Webhook or polling
    v
[MISSING] Telegram Bot running on VPS
    Currently: jarvis_mio (remoteme-based, in services/telegram/jarvis_mio/)
    Should be: PEPPER bot (services/telegram/pepper/) — the production bot
    Problem: No confirmed running bot on VPS that calls the diagnosis chain
    |
    | CapabilityClient.factory.diagnose()
    v
services/capabilities/factory.py  (FactoryCapability)
    |
    | Calls Groq API directly with problem description
    Problem: Does NOT read actual PLC state before calling the LLM
    The real path should go through the Jarvis node first
    |
    | HTTP POST to PLC Laptop Jarvis Node :8765
    v
JARVIS NODE on PLC Laptop (100.72.2.99:8765)
    |
    | runs shell: python plc-client-factoryio read_state()
    v
services/plc-modbus/backend/  (FastAPI on port 8001)
    |
    | GET /api/plc/io
    v
Micro 820 PLC (192.168.1.100:502 Modbus TCP)
    |
    | Coils 0-17, Registers 100+
    v
Factory I/O (simulation software on PLC laptop)
```

### The Correct Wired Path (What Should Exist)

```
Phone -> Telegram -> PEPPER/Gus bot -> CapabilityClient
                                           |
                               +-----------+-----------+
                               |                       |
                          caps.nodes              caps.factory
                          .shell(plc,             .diagnose()
                          read plc io)                |
                               |                       |
                               v                       v
                        plc-modbus /api/plc/io    Groq/Claude/OpenAI
                               |                       |
                               v                       |
                        Tag values ------------------>LLM prompt
                                                       |
                                                       v
                                                  Diagnosis text
                                                       |
                                                       v
                                               Telegram reply to Mike
```

### The Current Gap

`services/capabilities/factory.py` at line 57 takes a `problem` string and an optional `io_state` dict. The bot calling it must pass the current PLC tag values in the `io_state` argument. If the bot does not first call `caps.nodes.shell("plc", read_plc_io)` and attach the result, the LLM is diagnosing blindly without knowing actual machine state.

`services/diagnosis/main.py` handles this correctly — it reads the PLC via Jarvis node shell before calling the LLM. But the diagnosis service runs on port 8200 and is not guaranteed to be running on the VPS, and the bots are not confirmed to be calling it.

**The single most important wiring task is:** ensure the running Telegram bot calls `diagnosis/main.py` (or reconstructs that call pattern) so the LLM always sees real PLC tag values.

---

## Part 2: Service Inventory — Working vs Scaffolded vs Missing

### Working (Tested, Deployable)

| Service | Path | Port | What It Does |
|---------|------|------|--------------|
| PLC Modbus Backend | `services/plc-modbus/backend/` | 8001 | FastAPI reading Micro 820 via Modbus TCP. Routes: `/api/plc/io`, `/api/plc/connect`, `/api/plc/write-coil`, `/api/setup/scan-network`. Has MockPLC mode via `PLC_USE_MOCK=true`. 162 tests passing. |
| Diagnosis Service | `services/diagnosis/main.py` | 8200 | FastAPI that reads PLC via Jarvis node shell, then calls Groq LLM. Working but no automated tests and not confirmed as a running systemd service. |
| CapabilityClient | `services/capabilities/` | N/A | Python library used by bots. Seven capabilities: factory, nodes, memory, voice, github, photos, telemetry. The factory capability calls Groq/Claude/OpenAI. The nodes capability calls Jarvis nodes. Both work in isolation. |
| Troubleshoot Engine | `services/troubleshoot/engine/` | 8300 (assumed) | YAML-driven guided troubleshooting workflow engine. Supports question/advice/await_photo/vision_classify/escalate_llm node types. Works with the two existing workflows in `services/troubleshoot/workflows/`. Adapter wired to Telegram via `adapters/telegram_bot.py`. |
| Brain (Mem0+pgvector) | `services/brain/` | 8500 | Mem0 memory service backed by Neon PostgreSQL with pgvector. Gemini embeddings, Groq LLM for fact extraction. Has ingest webhook. Works but only wired to bots that explicitly import CapabilityClient. |
| PLC Monitor | `services/plc_monitor/` | N/A (daemon) | Async daemon that polls Matrix API for incidents, runs twin comparator (Factory I/O vs PLC expected state), sends Telegram alerts via `telegram_alerter.py`. Has CosmosClient integration stub. Well-structured but requires Matrix API to be running. |
| Conveyor Relay | `services/conveyor-relay/relay.py` | 8080 (assumed) | HTTP relay + WebSocket for conveyor HMI. Has a polished HMI in `static/index.html`. |
| Antfarm Workflows | `antfarm/workflows/` | N/A | Nine workflow YAML files defining multi-agent pipelines. The incident-response workflow is well-specified. Workflows reference real service endpoints. Not confirmed as actively running. |

### Scaffolded But Not Wired

| Component | Path | Status | What Is Missing |
|-----------|------|--------|-----------------|
| PEPPER Bot | `services/telegram/pepper/` | Directory structure exists, `intelligence/` and `tools/` subdirectories present but empty | The actual bot Python file. This is described in docs as the production bot but has no implementation. |
| Matrix API | `services/matrix/app.py` | The file is referenced extensively in workflows and by PLCMonitor but the file does not exist in the current checkout | The FastAPI service that stores tag snapshots, incidents, and insights. PLCMonitor and the incident-response workflow both depend on this. |
| Cosmos Agent | `cosmos/agent.py` | Referenced in README as "scaffolded stub, not calling Cosmos API" | Real Cosmos API integration. Currently returns hardcoded responses. |
| Dashboard | `apps/dashboard/` | `NOT_IMPLEMENTED.md` explicitly says no working code | The single-pane-of-glass UI. Frontend directory exists but is empty. |
| Mission Control | `apps/mission-control/` | Backend exists, frontend has `package-lock.json` (Node project initialized) but unclear if it runs | A working web UI for cluster management. |
| LLM Router | `services/llm-router/` | Directory listed in services/ but empty or near-empty | The layer-based routing logic from README (Layer 0 KB check -> Layer 1 -> Layer 2 -> Layer 3). Currently the factory capability just tries providers in order; there is no architectural router. |
| Worker Enrichment | `workers/` | Directory exists in status listing | Background enrichment workers. Unknown state. |
| Skills Service | `services/skills/` | Directory listed | MCP skill server. Unknown state. |

### Confirmed Missing (No Code)

| Component | Priority | Why |
|-----------|----------|-----|
| WhatsApp Adapter | Low (roadmap) | Telegram is working and sufficient for demo |
| Layer 0 Vector KB | High | The entire "intelligence downward" principle requires this |
| Workflow Capture | High | Converting successful AI traces to Layer 0 deterministic code |
| Unified Docker Compose | Medium | All services need orchestrated startup |
| CI/CD Pipeline | Medium | No GitHub Actions exists |
| Edge LLM on Pi | Low (roadmap) | No Pi deployed yet |
| Local GPU Server | Low (roadmap) | Vast.ai is the bridge until bare metal GPU exists |
| Layer 1/2 LLM endpoints | Medium | BRAVO node has Ollama :11434 but not wired into routing |

---

## Part 3: Deployment Topology — What Runs Where

### Current Topology (March 2026)

```
TAILSCALE MESH (all devices connected)

VPS (100.68.120.99 / root@100.68.120.99)
    /opt/openclaw/          OpenClaw gateway (systemd: openclaw, port 8340)
    ?                       Friday bot (systemd: friday-bot, status unknown)
    ?                       Diagnosis service (port 8200, not confirmed as systemd)
    n8n (port 5678)         Running per docs
    Flowise (port 3000)     Running per docs
    Plane (port 8000)       Running per docs (project management)
    RemoteMe API (port 8100) Running per docs

PLC Laptop (100.72.2.99 / hharp@LAPTOP-0KA3C70H)
    Windows 11
    Factory I/O             Running (simulation software)
    Micro 820               Connected via USB/Ethernet to 192.168.1.100:502
    Jarvis Node (:8765)     On-demand (not a persistent service)
    plc-modbus backend      Runs on port 8001 when started

Travel Laptop (100.83.251.23 / miguelomaniac)
    Windows 11 / macOS
    Claude Code             Active development
    Jarvis Node (:8765)     On-demand
    Development services    On-demand

Mac Mini Cluster (Lake Wales FL — LAN only, not Tailscale)
    ALPHA  (192.168.1.10)   Orchestrator, SMB host, Claude Code
    BRAVO  (192.168.1.11)   Ollama :11434 (model server)
    CHARLIE (192.168.1.12)  Qdrant :8000 (vector DB)

Raspberry Pi (192.168.1.30)
    RESERVED                No services deployed yet
```

### Target Topology (Production-Ready Demo)

```
VPS (always-on, systemd-managed)
    Port 8200  factorylm-diagnosis   (currently diagnosis/main.py)
    Port 8340  openclaw              (already running)
    Port 8765  jarvis-node           (currently on-demand only)
    Bot        pepper/gus bot        (telegram, needs to be wired)

PLC Laptop (Windows services or Task Scheduler)
    Port 8001  plc-modbus backend    (currently on-demand)
    Port 8765  jarvis-node           (currently on-demand)
    Auto-start Factory I/O scene

Mac Mini BRAVO
    Port 11434  Ollama               (Layer 2 LLM, currently unrouted)

Mac Mini CHARLIE
    Port 8000   Qdrant               (Layer 0 vector KB, currently empty)
```

---

## Part 4: The Full Demo Flow — End to End

### What Works Right Now (Demo-Ready Path)

```
1. Mike sends Telegram message to @FactoryLMBot or whichever bot is running
2. Bot receives message (IF Jarvis node on VPS is running and bot is configured)
3. Bot calls CapabilityClient.factory.diagnose(message)
4. FactoryCapability calls Groq API with the message text alone
5. Groq returns a diagnosis (generic, no real PLC data)
6. Bot sends response to Mike
```

This path works but produces low-quality diagnoses because step 4 has no actual PLC state.

### What the Full Loop Requires

```
1. Mike sends Telegram message
2. PEPPER/Gus bot on VPS receives it
3. Bot determines this is a factory question (keyword routing or LLM intent)
4. Bot calls diagnosis/main.py POST /diagnose with the question
5. Diagnosis service calls Jarvis node on PLC laptop GET /system-info
6. Diagnosis service calls Jarvis node shell: python read_plc_state.py
7. PLC state comes back: coils[0-17], registers[100+]
8. Diagnosis service builds prompt: [system prompt] + [plc state] + [question]
9. Groq Llama-3.1-70b returns diagnosis
10. Diagnosis service returns JSON to bot
11. Bot formats and sends to Mike via Telegram
```

### What Must Be Verified to Make Step 6 Work

The shell command in `services/diagnosis/main.py` at line 62 calls:

```
python -c "from factorylm_plc import create_plc_client; ..."
```

This requires `factorylm_plc` to be installed on the PLC laptop. The package lives in `services/plc-modbus/src/factorylm_plc/`. It must be `pip install -e .` on the PLC laptop inside whatever Python environment the Jarvis node runs under.

Alternatively, the simpler path for the demo is to call the already-running plc-modbus backend directly:

```python
# In diagnosis/main.py — replace the shell call with:
r = requests.get("http://100.72.2.99:8001/api/plc/io", timeout=5)
io_data = r.json()
# Format coils and registers into a readable string for the LLM prompt
```

This eliminates the shell dependency and uses the production FastAPI endpoint.

---

## Part 5: What Is Missing to Make the Full Demo Work

Ordered by blocking impact:

### P0 — Blockers (Demo Cannot Run Without These)

**P0.1: plc-modbus backend must auto-start on PLC laptop**

File: `services/plc-modbus/backend/main.py`
The backend must be running before the diagnosis chain can work.
Action: Create a Windows Task Scheduler entry or startup script that runs `uvicorn backend.main:app --host 0.0.0.0 --port 8001` at login.

**P0.2: Diagnosis service must be a running systemd service on VPS**

File: `services/diagnosis/main.py`
Currently not confirmed as a persistent service. The bot calling `/diagnose` will fail if this is not running.
Action: Create `/etc/systemd/system/factorylm-diagnosis.service` on the VPS, run with `doppler run -- uvicorn diagnosis.main:app --host 0.0.0.0 --port 8200`.

**P0.3: Diagnosis service must read real PLC tags (not shell)**

File: `services/diagnosis/main.py`, function `get_plc_state()` at line 53
The current implementation calls a shell command that depends on a Python package being installed in the right place. Replace with a direct HTTP call to `http://100.72.2.99:8001/api/plc/io`.

**P0.4: A Telegram bot on the VPS must call the diagnosis service**

The Telegram bot that Mike messages needs to detect factory questions and call `POST http://localhost:8200/diagnose`. The capabilities chain can be used, or the bot can call the diagnosis service directly. There is currently no confirmed bot doing this end-to-end.
Action: Wire the Friday bot or deploy `services/troubleshoot/adapters/telegram_bot.py` with the diagnosis intent handler.

**P0.5: Jarvis node must be a persistent service on PLC laptop**

The Jarvis node at port 8765 is documented as "on-demand." For the demo, the diagnosis service needs the node to be always available.
Action: Create a startup task on the PLC laptop that runs the Jarvis node.

### P1 — Quality (Demo Runs But Looks Amateur Without These)

**P1.1: Matrix API must exist**

File: `services/matrix/app.py` — file is missing despite being referenced extensively
The PLCMonitor, incident-response workflow, and Antfarm pipelines all reference `http://100.72.2.99:8000/api/incidents`. Without it, the incident-response loop cannot store data.
Action: Build a minimal Matrix API: `/api/tags`, `/api/incidents`, `/api/insights`. This is a 150-line FastAPI app.

**P1.2: PLC state must be continuously polled and cached**

Currently the diagnosis service reads PLC state synchronously on each request. For the demo, a 5-second background poll loop that caches tag values (following the pattern in `services/plc_monitor/monitor.py`) would make responses much faster and more reliable.

**P1.3: Conveyor relay HMI must be accessible from browser**

File: `services/conveyor-relay/static/index.html`
This is a polished HMI. It needs `relay.py` to be running and pointing at the plc-modbus backend.
Action: Confirm `relay.py` starts and the HMI URL is shareable during demo.

### P2 — Production Hardening

**P2.1: Unified Docker Compose**

All Python services (diagnosis, brain, troubleshoot, matrix, conveyor-relay) should start with one command via Docker Compose. Currently each is started manually.

**P2.2: Doppler secrets on all services**

All services should use `doppler run -- uvicorn ...` rather than `.env` files or hardcoded keys.

**P2.3: Health check dashboard**

A simple script or page that checks all endpoints in one call:
- `http://100.72.2.99:8001/health` (plc-modbus)
- `http://100.72.2.99:8765/health` (jarvis node)
- `http://100.68.120.99:8200/health` (diagnosis)
- `http://100.68.120.99:8340/` (openclaw)

**P2.4: CI/CD via GitHub Actions**

No pipeline exists. Minimum viable: run pytest on push to main.

---

## Part 6: Intelligence Flows Downward — Concrete Implementation Plan

The vision says: "Day 1 is Cloud AI. Day 60 is instant deterministic code." This section explains how to build that pipeline concretely, using what already exists.

### The Three Mechanisms Required

```
MECHANISM 1: Trace Capture
Every query to the LLM gets logged with:
  - The question asked
  - The PLC state at time of asking
  - The LLM response
  - Whether the user accepted the answer (feedback)

MECHANISM 2: Pattern Recognition
A background process scans the trace log looking for:
  - Same question asked more than 3 times
  - Same PLC state pattern associated with same answer
  - High-confidence answers (not edge cases)

MECHANISM 3: Workflow Promotion
When a pattern is confirmed, a deterministic workflow is created:
  - YAML file in services/troubleshoot/workflows/
  - The workflow engine (already built) runs it without LLM
  - Same question now costs $0 and responds in <100ms
```

### What Already Exists That Supports This

`services/troubleshoot/engine/workflows.py` — The workflow engine is fully built. It reads YAML files with question/advice/escalate_llm node types. The `escalate_llm` node type is the escape hatch back to the LLM. This means every troubleshooting tree starts deterministic and only escalates when needed.

`services/brain/ingest.py` — The Mem0 ingest webhook accepts arbitrary content with metadata. Every LLM diagnosis should also be ingested here: `POST /ingest` with source="diagnosis", tags=["plc", "conveyor"], metadata including the PLC state snapshot.

`services/troubleshoot/workflows/photo_triage.yaml` and `mechanical_bolted_joint.yaml` — Two real workflows exist showing the structure. They prove the engine works. More workflows should be added from observed LLM interactions.

### The Concrete Build Sequence

**Step A: Add trace logging to diagnosis/main.py**

After every LLM diagnosis call, write a trace record:
```python
trace = {
    "question": request.question,
    "plc_state": plc_data,
    "diagnosis": diagnosis,
    "timestamp": datetime.utcnow().isoformat(),
    "latency_ms": latency,
    "llm_model": GROQ_MODEL,
}
# Append to services/diagnosis/traces/YYYY-MM-DD.jsonl
```

This is five lines of code. Do it now.

**Step B: Add feedback signal to Telegram bot**

After the bot sends a diagnosis, add two inline keyboard buttons:
- "That helped" (thumbs up)
- "That was wrong" (thumbs down)

When a user taps the button, the bot calls `POST /ingest` to the brain service with the feedback and the original diagnosis. This creates the ground truth signal for pattern recognition.

**Step C: Weekly trace review workflow**

Create a scheduled Antfarm workflow (or cron job) that:
1. Reads all traces from the past week
2. Groups by question similarity (using the brain memory search)
3. Identifies questions asked 3+ times with the same resolution
4. Drafts a YAML workflow file for the troubleshoot engine
5. Posts the draft to Mike via Telegram for approval before committing

This is the CLUSTER.md "6AM pattern scan" applied specifically to factory diagnoses.

**Step D: Promote to Layer 0**

Once a workflow YAML is approved:
1. Drop it into `services/troubleshoot/workflows/`
2. The workflow engine picks it up automatically on restart (it scans the directory)
3. The Telegram bot's intent router checks the workflow engine before calling the LLM
4. If the workflow engine has a match, it runs the workflow and returns the answer without an LLM call

The Layer 0 knowledge base grows one workflow at a time, each representing a question that was answered correctly by the LLM enough times to trust the pattern.

### The LLM Router (Currently Missing)

`services/llm-router/` exists as a directory but has no implementation. This is the gating component for the intelligence layers. A minimal implementation:

```python
async def route_query(question: str, context: dict) -> str:
    # Layer 0: Check KB / workflow engine first
    workflow_match = workflow_engine.match(question)
    if workflow_match and workflow_match.confidence > 0.9:
        return workflow_engine.run(workflow_match)

    # Layer 0: Check Brain (Mem0 vector search)
    memory_match = await brain.query(question)
    if memory_match and memory_match[0].score > 0.85:
        return memory_match[0].memory

    # Layer 2: BRAVO node Ollama (local, no cost, air-gappable)
    if bravo_available():
        return await ollama.generate(question, context)

    # Layer 3: Cloud AI (Groq first, then Anthropic)
    return await cloud_ai.diagnose(question, context)
```

This file should live at `services/llm-router/router.py` and be imported by the diagnosis service instead of calling Groq directly.

---

## Part 7: Priority Order for Production-Readiness

### Sprint 1: Close the Demo Loop (1-2 days)

Goal: Mike sends a Telegram message and gets a real diagnosis with actual PLC state, reliably, every time.

1. Verify plc-modbus backend starts on PLC laptop boot (Task Scheduler entry)
2. Verify Jarvis node starts on PLC laptop boot
3. Update `services/diagnosis/main.py` `get_plc_state()` to call `http://100.72.2.99:8001/api/plc/io` directly instead of via shell
4. Create systemd service for diagnosis on VPS: `factorylm-diagnosis.service`
5. Confirm the Friday bot or another running bot calls `POST /diagnose` for factory questions
6. End-to-end test: Telegram message -> diagnosis with real PLC tags -> response

**Acceptance criterion:** Send "why is the conveyor stopped?" on Telegram and get a response that references actual coil values from the Micro 820.

### Sprint 2: Observability and Stability (3-5 days)

Goal: The system can be monitored and does not require manual restart.

7. Add trace logging to diagnosis service (JSONL file per day)
8. Build minimal Matrix API (`services/matrix/app.py`) with four endpoints
9. Wire PLCMonitor to Matrix API so incidents are stored
10. Create a health-check script that pings all endpoints and posts results to Telegram
11. Set up Docker Compose for VPS services
12. Add feedback buttons to Telegram bot responses

**Acceptance criterion:** System runs for 24 hours without manual intervention. All logs are visible. Mike can check system health via one Telegram command.

### Sprint 3: Intelligence Capture (1 week)

Goal: Every LLM interaction is captured and can be promoted to deterministic code.

13. Wire brain ingest to diagnosis service (every diagnosis stored in Mem0)
14. Build the weekly trace review Antfarm workflow
15. Write three more troubleshoot YAML workflows based on known PLC fault patterns
16. Build the LLM router in `services/llm-router/router.py`
17. Route the diagnosis service through the LLM router instead of calling Groq directly

**Acceptance criterion:** Ten diagnoses have been captured. Two have been promoted to Layer 0 workflows. Those two questions now respond in under 100ms with no LLM call.

### Sprint 4: Cluster Integration (1 week)

Goal: BRAVO node Ollama is wired in as Layer 2.

18. Confirm Ollama is running on BRAVO (192.168.1.11:11434)
19. Add BRAVO to the NodesCapability configuration
20. Add Ollama layer to the LLM router
21. Pull a suitable model on BRAVO (Llama-3.1-8B is a good start, Llama-3.1-70B if VRAM allows)
22. Test Layer 2 path: same question routed to BRAVO instead of Groq

**Acceptance criterion:** Disconnect internet on VPS. Factory questions still get answered via BRAVO.

### Sprint 5: CHARLIE Vector KB (2 weeks)

Goal: Qdrant on CHARLIE stores vectorized PLC manuals and fault code libraries.

23. Confirm Qdrant is running on CHARLIE (192.168.1.12:8000)
24. Create a collection for equipment documentation
25. Ingest the Micro 820 manual and Factory I/O documentation
26. Add Qdrant search to the LLM router as the first Layer 0 check
27. Populate with fault codes and their known solutions

**Acceptance criterion:** "What does fault code E01 mean?" returns the correct answer from Qdrant in under 200ms with no LLM call.

---

## Part 8: Architectural Decisions and Rationale

### Why diagnosis/main.py Is the Right Shape

The diagnosis service at `services/diagnosis/main.py` is architecturally correct. It is a FastAPI service that:
- Accepts a natural language question
- Enriches it with real PLC state
- Calls an LLM
- Returns structured JSON

This is exactly the pattern that the LLM router should call. The service should stay as the central "factory intelligence" endpoint. All bots call this service. The service's internals evolve (better PLC reading, LLM routing, KB lookups) without changing the bot interface.

### Why CapabilityClient.factory Is a Local Shortcut

`services/capabilities/factory.py` calls the LLM directly without reading PLC state. This is useful for quick tests but should not be used in production for factory diagnosis. In production, the bot should call the diagnosis service. The factory capability could be refactored to delegate to the diagnosis service rather than calling the LLM directly.

### Why the Troubleshoot Engine Is Underutilized

`services/troubleshoot/engine/` is the most complete "intelligence downward" mechanism in the repo and it is almost invisible in the current architecture. The diagnosis service calls an LLM. The troubleshoot engine runs YAML workflows. These are parallel, not integrated. The integration: the diagnosis service should check the troubleshoot engine first (as a Layer 0 check) before calling the LLM.

### Why Multiple Telegram Bots Exist

The repo has `jarvis_mio`, `pepper`, and references to `friday`, `gus`, and other bots. This is technical debt from iteration. The production decision should be: one bot per purpose.

- Gus: Factory diagnosis (industrial workers)
- PEPPER: Mike's personal assistant (all capabilities)
- Friday: General assistant (can be deprecated or merged with PEPPER)

The troubleshoot engine's `services/troubleshoot/adapters/telegram_bot.py` is the cleanest adapter. It should be the bot that handles factory questions.

### Why the Cluster Architecture Matters Now

ALPHA/BRAVO/CHARLIE provide:
- BRAVO: A Layer 2 LLM that is free, fast, and air-gappable. This eliminates Groq costs as the knowledge base grows.
- CHARLIE: A Layer 0 vector database. This is where PLC manuals, fault codes, and captured workflows should live.

The cluster is defined in CLUSTER.md but is not used by any running service today. Connecting the LLM router to BRAVO and CHARLIE is the most impactful architectural step after closing the demo loop.

---

## Part 9: Files That Must Be Created (New Work Required)

The following files do not exist and must be created:

| File | Purpose | Estimated Size |
|------|---------|----------------|
| `services/matrix/app.py` | Matrix API: tag storage, incidents, insights | 150 lines |
| `services/llm-router/router.py` | Layer-based query routing | 120 lines |
| `services/diagnosis/traces/` | Directory for JSONL trace logs | (directory) |
| `antfarm/workflows/trace-to-workflow.yaml` | Weekly pattern promotion workflow | 80 lines |
| `docker-compose.yml` | Unified service orchestration | 100 lines |
| `/etc/systemd/system/factorylm-diagnosis.service` | VPS systemd service | 20 lines |
| `scripts/health_check.py` | Ping all endpoints, report to Telegram | 60 lines |
| PLC laptop startup script | Start plc-modbus and jarvis-node on boot | 10 lines |

---

## Part 10: The One-Page Summary for a Solo Founder

**What you have:**

The PLC communication stack is production-grade. The troubleshoot engine is production-grade. The capabilities layer is a clean abstraction. The data flow architecture is correct on paper. The Antfarm workflow definitions are detailed and realistic.

**What is broken:**

The services do not start automatically. The diagnosis service reads PLC state via a fragile shell command instead of the HTTP endpoint that is right there. There is no confirmed bot on the VPS that calls the full diagnosis chain with real PLC state. The Matrix API that everything references does not exist.

**What to do first:**

1. Fix `get_plc_state()` in `services/diagnosis/main.py` to call `http://100.72.2.99:8001/api/plc/io`
2. Make plc-modbus backend start on PLC laptop boot
3. Make diagnosis service a systemd service on VPS
4. Confirm the Telegram bot calls `/diagnose` endpoint for factory questions
5. Test end-to-end with real PLC hardware

That is four changes and one test. Once done, the demo works reliably and the "text your factory, AI tells you what is wrong" story is true.

**What to do next to implement intelligence downward:**

Add trace logging to the diagnosis service today (five lines). That starts the data pipeline. After 30 days of traces, patterns will be visible. Use the troubleshoot engine (already built) to codify those patterns as YAML workflows. Route through the LLM router instead of directly to Groq. Watch the Layer 3 bill decrease as Layer 0 coverage grows.

**The two-sentence architecture:**

A Telegram bot receives factory questions, enriches them with live PLC tag values from the Modbus backend, and sends them to a Groq LLM that produces actionable diagnoses. Over time, successful diagnoses are captured as YAML workflows and served deterministically by the troubleshoot engine, eliminating the LLM call entirely.

---

*This document was produced by full analysis of the factorylm monorepo on 2026-03-04.*
*All file paths are relative to the monorepo root: `C:\Users\hharp\OneDrive\Desktop\FactoryLM`*
*Next review: After Sprint 1 completion*
