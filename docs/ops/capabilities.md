# FactoryLM Capability Ledger

> Cross-repo capability index for the entire FactoryLM / Jarvis ecosystem.
> Updated: 2026-02-17

---

## 1. OpenClaw / Jarvis (`Mikecranesync/openclaw`)

**Location:** VPS `/opt/openclaw/` (100.68.120.99:8340)
**Architecture:** FastAPI + intent-based LLM routing + skill dispatch

### Skills

| # | Capability | Intent | Skill | Status |
|---|-----------|--------|-------|--------|
| 1 | PLC fault diagnosis | DIAGNOSE | diagnose | production |
| 2 | Live PLC tag status | STATUS | status | production |
| 3 | Photo analysis (Gemini vision) | PHOTO | photo | production |
| 4 | CMMS work orders | WORK_ORDER | work_order | production |
| 5 | Web search (Perplexity Sonar) | SEARCH | search | production |
| 6 | Admin/health dashboard | ADMIN, HELP | admin | production |
| 7 | General chat | CHAT, UNKNOWN | chat | production |
| 8 | Remote shell execution | SHELL | shell | merged (PR #2) |
| 9 | KB-enriched chat | CHAT | chat | merged (PR #2) |
| 10 | KB-enriched diagnosis | DIAGNOSE | diagnose | merged (PR #2) |
| 11 | Maintenance LLM (Ollama) | -- | -- (connector) | merged (PR #2) |
| 12 | Wiring diagrams | DIAGRAM | diagram | merged (PR #3) |
| 13 | Source URL linking | CHAT | chat | merged (PR #3) |

### Telegram Gateway

| # | Capability | Status |
|---|-----------|--------|
| 14 | TTS voice replies (edge-tts, JennyNeural) | production |
| 15 | STT transcription (Groq Whisper v3 turbo) | production |
| 16 | Emoji acknowledgment (👀 on receipt) | production |
| 17 | Markdown formatting with triple fallback | production |
| 18 | Message chunking (4096 char limit) | production |

### LLM Routing

| Intent | Primary | Fallback(s) |
|--------|---------|-------------|
| DIAGNOSE | anthropic | groq, gemini |
| PHOTO | gemini | anthropic |
| WORK_ORDER | anthropic | groq |
| DIAGRAM | openrouter | anthropic, groq |
| CHAT | groq | openrouter, openai |
| STATUS | groq | -- |
| SEARCH | groq | -- |
| ADMIN | groq | -- |

### Connectors

| Connector | Target | Feature Flag | Status |
|-----------|--------|-------------|--------|
| Matrix API | 100.72.2.99:8000 | always on | production |
| Jarvis Node (PLC laptop) | 100.72.2.99:8765 | always on | production |
| Jarvis Node (Travel laptop) | 100.83.251.23:8765 | always on | production |
| Knowledge Base | localhost:5432/rivet | `kb_enabled` | merged (PR #2) |
| Maintenance LLM | 100.72.2.99:11434 | `maint_llm_enabled` | merged (PR #2) |
| PLC (direct Modbus) | 192.168.1.100:502 | -- | prototype |
| CMMS | configurable | -- | experimental |

### Fault Detection (Rule-Based, Zero-Latency)

| Code | Severity | Condition |
|------|----------|-----------|
| E001 | EMERGENCY | E-stop active |
| M001 | CRITICAL | Motor overcurrent (>5A) |
| M002 | CRITICAL | Motor stopped unexpectedly |
| M003 | WARNING | Motor speed mismatch |
| T001 | CRITICAL | High temperature (>80C) |
| T002 | WARNING | Elevated temperature (65-80C) |
| C001 | CRITICAL | Conveyor jam (both sensors) |
| P001 | WARNING | Low pneumatic pressure (<60 PSI) |

---

## 2. Monorepo Services (`Mikecranesync/factorylm`)

| # | Service | Path | Type | Port | Status |
|---|---------|------|------|------|--------|
| 19 | Matrix API | `services/matrix/app.py` | FastAPI | 8000 | production |
| 20 | Factory I/O Bridge | `sim/factoryio_bridge.py` | poller | -- | production |
| 21 | PLC Simulator | `sim/plc_simulator.py` | simulator | -- | production |
| 22 | Cosmos Agent | `cosmos/agent.py` | agent | -- | experimental |
| 23 | Cosmos Watcher | `cosmos/watcher.py` | worker | -- | experimental |
| 24 | Cosmos Client | `cosmos/client.py` | library | -- | working |
| 25 | Conveyor Fault Library | `diagnosis/conveyor_faults.py` | library | -- | production |
| 26 | Diagnosis Prompts | `diagnosis/prompts.py` | prompts | -- | production |
| 27 | Diagnosis Service | `services/diagnosis/main.py` | FastAPI | 8200 | working |
| 28 | PLC Copilot | `services/plc-copilot/` | Telegram bot | -- | production (Docker) |
| 29 | PLC Modbus Backend | `services/plc-modbus/backend/` | FastAPI | 8000 | production |
| 30 | PLC Modbus Edge Server | `services/plc-modbus/factorylm-edge/` | edge | -- | production |
| 31 | Core LLM Library | `core/src/factorylm/llm/` | library | -- | production |

**Matrix API endpoints:** `/api/tags`, `/api/incidents`, `/api/insights`, `/api/video/clips`, `/api/video/analyses`
**Cosmos model:** `nvidia/cosmos-reason2-8b`, fallback: `meta/llama-3.1-70b-instruct`
**Core LLM providers:** Groq, DeepSeek, Claude, FLM (planned)

---

## 3. Monorepo Workers (`workers/`)

38+ Celery workers orchestrated via Redis. Key workers:

| # | Worker | Purpose | Status |
|---|--------|---------|--------|
| 32 | manual_hunter | Equipment manual hunting/indexing | experimental |
| 33 | synthetic_user | 24/7 KB builder from synthetic queries | experimental |
| 34 | alarm_triage | Alarm classification and routing | experimental |
| 35 | quality_gate | @quality_gated decorator for content | experimental |
| 36 | demo_director | YC demo automation (OBS, cameras) | experimental |
| 37 | plc_sync | PLC I/O state synchronization | experimental |
| 38 | edge_gateway | Edge gateway log monitoring | experimental |
| 39 | monkey | Chaos testing / fault injection | experimental |
| 40 | github_scrubber | Continuous repo scanning for KB | experimental |
| 41 | article_publisher | Scientific article generation | experimental |
| 42 | content_capture | YouTube automation | experimental |

---

## 4. Monorepo Brain (`brain/`)

| # | Agent | Purpose | Status |
|---|-------|---------|--------|
| 43 | Hammurabi | Quality judgment (quality/novelty/actionable/consistency scoring, thresholds, Claude-powered) | experimental |
| 44 | Herodotus | Knowledge recorder and archiver | experimental |

---

## 5. Monorepo Collectors (`collectors/`)

| # | Collector | Protocol | Status |
|---|-----------|----------|--------|
| 45 | AB Collector | Allen-Bradley native | experimental |
| 46 | S7 Collector | Siemens S7 | experimental |
| 47 | Modbus Collector | Modbus TCP/RTU | experimental |

---

## 6. Monorepo Analytics (`analytics/`)

| # | Component | Purpose | Status |
|---|-----------|---------|--------|
| 48 | Baseline Builder | Learn normal operational patterns | experimental |
| 49 | Drift Detector | Anomaly detection from baseline | experimental |
| 50 | Pattern Embedder | Similarity matching via embeddings | experimental |

---

## 7. Monorepo Video (`video/`)

| # | Component | Purpose | Status |
|---|-----------|---------|--------|
| 51 | Cosmos Video Analyzer | Video-grounded fault analysis | experimental |
| 52 | Highlight Selector | Clip selection for demo reels | experimental |
| 53 | Video Ingester | Video file ingestion pipeline | experimental |

---

## 8. Voltron (`Mikecranesync/voltron`)

Competing/complementary distributed architecture. 61 passing tests, not yet in production.

| # | Component | Type | Purpose | Status |
|---|-----------|------|---------|--------|
| 54 | Matrix Controller | service | Central Telegram bot, node registry, task dispatch, PostgreSQL | planning |
| 55 | Distributed Nodes | agent | Offline-first SQLite, heartbeat, policy engine, read-only enforcement | planning |
| 56 | LLM Tier Router | library | Small brain (Groq Llama 3.3) / big brain (Claude Opus), cost tracking | planning |
| 57 | PLC Reader Tool | tool | Modbus TCP PLC reading from nodes | planning |
| 58 | Diagnostic Tool | tool | Run diagnostics on PLC state | planning |
| 59 | Knowledge Search Tool | tool | Search KB from nodes | planning |
| 60 | Web Search Tool | tool | Web search for troubleshooting | planning |

---

## 9. Jarvis Infrastructure

| # | Component | Repo | Purpose | Status |
|---|-----------|------|---------|--------|
| 61 | Jarvis Node / RemoteMe | `remoteme-jarvis-node` | FastAPI on port 8765 — shell exec, screenshots, file ops, notifications, message queue | production |
| 62 | JARVIS-IS-DEAD | `JARVIS-IS-DEAD` | Frozen v0.9.0 baseline, resurrection workflows, golden tests, behavior-to-code map | operational archive |
| 63 | Jarvis Workspace | `jarvis-workspace` | SOUL.md identity, MEMORY.md persistence, AGENTS.md procedures, heartbeat monitoring | operational |
| 64 | Archimedes Framework | `jarvis-workspace` | Multi-agent dev loop: Foreman → Workers → Hammurabi → Prometheus | experimental |

---

## 10. Standalone Products

| # | Product | Repo | Purpose | Status |
|---|---------|------|---------|--------|
| 65 | factorylm-plc-client | `factorylm-plc-client` | Modbus TCP library (v0.4.0), LLM4PLC ST code gen, MockPLC, verified register map | production |
| 66 | factorylm-core | `factorylm-core` | Unified LLM client (v0.1.0) — Groq/DeepSeek/Claude/FLM, cost tracking, streaming | production |
| 67 | IndustrialSkillsHub | `IndustrialSkillsHub` | Duolingo for maintenance techs — Next.js, bilingual ES/EN, gamified, 4 learning tracks | complete (needs hosting) |
| 68 | RideView | `resurrected-tools` | Torque stripe CV verification — Flask + OpenCV, PASS/WARN/FAIL classification | working |
| 69 | factorylm-cmms | `factorylm-cmms` | ISO 55000 CMMS — GitHub-native (Issues + Gists), PM frameworks research | concept |
| 70 | factorylm-landing | `factorylm-landing` | Marketing site (factorylm.com) — product pages, 3D configurator | production |

---

## 11. Jarvis-Exposed vs Not-Yet-Wired

### Wired into Jarvis today

- 9 OpenClaw skills (diagnose, status, photo, work_order, search, shell, diagram, chat, admin)
- 6 connectors (matrix, jarvis, knowledge, maintenance_llm, plc, cmms)
- Telegram gateway (TTS, STT, emoji ack, markdown, chunking)
- Fault detection engine (11 fault codes)
- Multi-provider LLM routing (Groq, Anthropic, Gemini, OpenRouter)

### On the shelf (exist in code, not wired into Jarvis)

| Capability | Repo | How to wire in |
|-----------|------|---------------|
| Cosmos Agent | factorylm | Trigger from diagnose skill on critical faults |
| Cosmos Watcher | factorylm | Run alongside Jarvis, feed insights back |
| Core LLM Library | factorylm-core | Replace Jarvis's LLM router with unified client |
| factorylm-plc-client | factorylm-plc-client | Replace basic pymodbus connector with mature library |
| Voltron LLM tiering | voltron | Adopt small/big brain routing in Jarvis |
| Voltron policy engine | voltron | Enforce immutable safety constraints |
| Collectors (AB/S7/Modbus) | factorylm | Multi-protocol PLC polling behind Jarvis |
| Analytics (drift/baseline) | factorylm | Predictive maintenance from Jarvis |
| Workers (manual_hunter, synthetic_user) | factorylm | Automated KB building |
| Hammurabi | factorylm | Quality gates on Jarvis responses |
| RideView | resurrected-tools | Visual QC skill: "Check torque stripe" |
| IndustrialSkillsHub | IndustrialSkillsHub | Training recommendations based on skill gaps |
| CMMS (GitHub-native) | factorylm-cmms | Work orders as GitHub Issues |

---

## 12. Open PRs

| PR | Repo | URL | Capabilities |
|----|------|-----|-------------|
| #3 | openclaw | https://github.com/Mikecranesync/openclaw/pull/3 | Wiring diagrams, source URL linking |
| #46 | factorylm | https://github.com/Mikecranesync/factorylm/pull/46 | E-stop incident creation + Cosmos analysis |
| #42 | factorylm | https://github.com/Mikecranesync/factorylm/pull/42 | Voltron/PEPPER bots, digital twins, telemetry (39K lines) |

## 13. Abandoned Capabilities

| PR | Repo | Title | Why |
|----|------|-------|-----|
| #13 | factorylm | Slack adapter | closed, never merged |
| #12 | factorylm | WhatsApp Business API adapter | closed, never merged |
| #40 | factorylm | PEPPER dual-mode bot v1 | superseded by #42 |
| #41 | factorylm | Cosmos Cookoff v1 | superseded by #43 |

---

## Related

- **Baseline**: [2026-02-16 Jarvis Baseline](baselines/2026-02-16_openclaw_jarvis_baseline.md)
- **Registry**: [registry.yaml](registry.yaml)
- **Traces**: [traces/](traces/)
- **OpenClaw**: https://github.com/Mikecranesync/openclaw
- **Voltron**: https://github.com/Mikecranesync/voltron
- **factorylm-core**: https://github.com/Mikecranesync/factorylm-core
- **factorylm-plc-client**: https://github.com/Mikecranesync/factorylm-plc-client
- **IndustrialSkillsHub**: https://github.com/Mikecranesync/IndustrialSkillsHub
- **JARVIS-IS-DEAD**: https://github.com/Mikecranesync/JARVIS-IS-DEAD
