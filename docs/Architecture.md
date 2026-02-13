# FactoryLM — Architecture Overview

**Last Updated:** 2026-02-12  
**Status:** Phase 1 — Repo Scan Complete  

---

## What This Project Is

FactoryLM is an **industrial AI platform** that helps factory technicians diagnose equipment problems. In plain English:

- A technician takes a photo of a machine or asks a question (via WhatsApp, Telegram, or a web dashboard)
- The system looks up the answer in a knowledge base of manuals, fault codes, and past fixes
- If the knowledge base doesn't have the answer, it asks an AI model (cloud or local)
- Over time, AI answers get turned into code so the same question never needs AI again

**It never writes to or controls equipment.** Read-only diagnostics only.

The repo is a **monorepo** managed by Turborepo, containing apps, services, shared packages, PLC clients, scripts, and documentation — all at different stages of completion.

---

## Maturity Map (What's Real vs. Planned)

| Component | Language | Status | Notes |
|-----------|----------|--------|-------|
| `core/` — LLM abstraction | Python | ✅ **Complete** | 148 tests, Groq/DeepSeek/Claude clients |
| `My-Ralph/` — Autonomous dev loop | Python + Bash | ✅ **Complete** | 321 tests, FastAPI API, v1.0.1 |
| `services/plc-modbus/` — PLC Modbus client | Python | ✅ **Working** | FastAPI backend, Micro 820 integration, edge server for Pi |
| `services/plc-copilot/` — Photo→CMMS bot | Python | ✅ **Working** | Telegram bot, Gemini Vision, Atlas CMMS integration |
| `plc-client/` — Generic PLC library | Python | ⚠️ **Partial** | Modbus/PLC modules, tests exist |
| `plc-client-factoryio/` — FactoryIO simulator | Python | ⚠️ **Partial** | Micro820 + FactoryIO + mock PLC clients |
| `apps/cmms/` — CMMS web app | Java + React/TS | ⚠️ **Forked, not rebranded** | Spring Boot API + React frontend, from grash-cmms |
| `apps/portal/` — Jarvis brain portal | Node.js | ⚠️ **VPS-specific** | Express server reading `/root/jarvis-workspace/brain` |
| `apps/dashboard/` | — | 🔴 **Placeholder** | README only |
| `apps/web/` | — | 🔴 **Stub** | Empty `src/components/` |
| `services/api/` | — | 🔴 **Placeholder** | README only |
| `services/assistant/` | — | 🔴 **Placeholder** | README only |
| `packages/auth/` | — | 🔴 **Placeholder** | README only |
| `packages/db/` | — | 🔴 **Placeholder** | README only |
| `packages/ui/` | — | 🔴 **Placeholder** | README only |
| `packages/config/` | JS | 🟡 **Minimal** | Just an ESLint config |
| `scripts/` | Mixed | ✅ **Utility** | VPS management, Honeycomb setup, Pi setup |

---

## High-Level Architecture

```
                    ┌─────────────────────────────────────┐
                    │         USER INTERFACES              │
                    │  WhatsApp · Telegram · Web Dashboard │
                    └──────────────┬──────────────────────┘
                                   │
                    ┌──────────────▼──────────────────────┐
                    │         MESSAGE ROUTER                │
                    │  (planned — not yet built)            │
                    └──────────────┬──────────────────────┘
                                   │
          ┌────────────────────────┼────────────────────────┐
          │                        │                        │
  ┌───────▼───────┐    ┌──────────▼──────────┐   ┌─────────▼─────────┐
  │  LAYER 0      │    │  LAYER 1            │   │  LAYER 2-3        │
  │  Knowledge    │    │  Edge LLM           │   │  Local GPU /      │
  │  Base (KB)    │    │  (Pi, Qwen 0.5B)    │   │  Cloud AI         │
  │  Vector DB    │    │  (planned)          │   │  (core/ clients)  │
  │  Workflows    │    │                     │   │  Groq, Claude,    │
  │  (planned)    │    │                     │   │  DeepSeek         │
  └───────────────┘    └─────────────────────┘   └───────────────────┘

          ┌────────────────────────────────────────────────┐
          │              PLC CONNECTIVITY (READ ONLY)       │
          │  plc-client · plc-client-factoryio · plc-modbus │
          │  Modbus TCP · EtherNet/IP · OPC UA              │
          │  Allen-Bradley Micro 820 + FactoryIO sim        │
          └────────────────────────────────────────────────┘

          ┌────────────────────────────────────────────────┐
          │              STANDALONE TOOLS                    │
          │  My-Ralph (autonomous dev loop API)             │
          │  PLC Copilot (Telegram photo→CMMS bot)          │
          │  Jarvis Portal (VPS brain viewer)                │
          │  CMMS (forked maintenance management app)       │
          └────────────────────────────────────────────────┘

          ┌────────────────────────────────────────────────┐
          │              OBSERVABILITY                      │
          │  Axiom (logs via Vector shippers)               │
          │  Honeycomb (traces via OTel SDK — just set up)  │
          └────────────────────────────────────────────────┘
```

---

## Directory Map

```
FactoryLM/
│
├── core/                          # Python — LLM abstraction layer ✅
│   ├── src/factorylm/
│   │   ├── llm/                   # Provider clients (groq, claude, deepseek, flm)
│   │   ├── config.py              # Env-based config loader
│   │   └── utils/                 # Shared utilities
│   ├── adapters/                  # Empty — future channel adapters
│   ├── models/                    # Empty — future data models
│   ├── services/                  # Empty — future business logic
│   ├── i18n/                      # Empty — future internationalization
│   └── tests/                     # 148 tests (unit + integration)
│
├── My-Ralph/                      # Autonomous AI dev loop ✅
│   ├── api/                       # FastAPI service (loop, monitor, import, logs)
│   ├── lib/                       # Bash library (circuit breaker, response analyzer)
│   ├── src/                       # Core bash scripts
│   ├── templates/                 # Project setup templates
│   └── tests/                     # 321 BATS + 34 pytest tests
│
├── services/
│   ├── plc-modbus/                # PLC Modbus client + FastAPI backend ✅
│   │   ├── src/factorylm_plc/    # Modbus client library (Micro820, FactoryIO, mock)
│   │   ├── backend/              # FastAPI: network scanner, PLC routes, WebSocket
│   │   ├── tools/                # CLI tools (plc_monitor, plc_logger)
│   │   └── factorylm-edge/      # Raspberry Pi edge server (Modbus TCP + GPIO)
│   ├── plc-copilot/               # Photo→CMMS Telegram bot ✅
│   │   └── photo_to_cmms_bot.py  # Gemini Vision + Atlas CMMS, single-file bot
│   ├── api/                       # Placeholder (README only) 🔴
│   └── assistant/                 # Placeholder (README only) 🔴
│
├── apps/
│   ├── cmms/                      # Forked CMMS (grash-cmms) ⚠️ not rebranded
│   │   ├── api/                  # Java Spring Boot (pom.xml, 650 .java files)
│   │   └── frontend/             # React 18 + MUI + TypeScript (169 .ts files)
│   ├── portal/                    # Jarvis brain portal (Express.js, VPS-specific) ⚠️
│   ├── dashboard/                 # Placeholder (README only) 🔴
│   └── web/                       # Stub (empty src/components/) 🔴
│
├── plc-client/                    # Generic PLC library (Python) ⚠️
│   └── src/factorylm_plc/       # modbus/ + plc/ modules
│
├── plc-client-factoryio/          # FactoryIO simulator client (Python) ⚠️
│   └── src/factorylm_plc/       # Micro820, FactoryIO, mock, connection manager
│
├── packages/                      # Shared JS packages (Turborepo)
│   ├── config/                   # ESLint config only
│   ├── auth/                     # Placeholder 🔴
│   ├── db/                       # Placeholder 🔴
│   └── ui/                       # Placeholder 🔴
│
├── scripts/
│   ├── honeycomb/                # OTel tracing setup (just created)
│   ├── pi-setup/                 # Raspberry Pi first-run script
│   ├── ralph/                    # Ralph utility scripts
│   └── *.py                      # VPS management (fix configs, add providers, etc.)
│
├── docs/
│   ├── Architecture.md           # ← THIS FILE
│   ├── OPENCLAW_INSTANCES.md     # OpenClaw bot instance map
│   ├── UNBOXING_TO_LLM_GUIDE.md # Hardware setup guide
│   ├── adapters/                 # WhatsApp setup docs
│   └── specs/                    # Spec template
│
├── pics/                          # Images/screenshots
│
├── README.md                      # THE VISION (canonical, v0.25)
├── CLAUDE.md                      # AI agent instructions
├── MEMORY.md                      # Session memory / context graph
├── MIGRATION.md                   # Migration notes
├── RESUME_PROMPT.md               # Resume instructions for agents
├── Ewon_replacer.md               # Ewon device replacement notes
├── PRD-001 through PRD-005        # Product Requirements Documents
├── package.json                   # Turborepo root workspace
└── turbo.json                     # Turborepo pipeline config
```

---

## Entrypoints (Things You Can Actually Run)

### APIs

| What | Command | Port | Status |
|------|---------|------|--------|
| PLC Modbus API | `uvicorn backend.main:app --reload` (in `services/plc-modbus/`) | 8000 | ✅ Working |
| My-Ralph API | `python -m uvicorn api.main:app --reload` (in `My-Ralph/`) | 8000 | ✅ Working |
| CMMS API | `./mvnw spring-boot:run` (in `apps/cmms/api/`) | ? | ⚠️ Forked, untested in this repo |
| Jarvis Portal | `node server.js` (in `apps/portal/`) | 3001 | ⚠️ VPS-specific (reads `/root/jarvis-workspace`) |

### Bots

| What | Command | Status |
|------|---------|--------|
| PLC Copilot (Telegram) | `python photo_to_cmms_bot.py` (in `services/plc-copilot/`) | ✅ Working — needs env vars |

### CLI Tools

| What | Command | Status |
|------|---------|--------|
| PLC Monitor | `python tools/plc_monitor.py` (in `services/plc-modbus/`) | ✅ Needs PLC on network |
| PLC Logger | `python tools/plc_logger.py` (in `services/plc-modbus/`) | ✅ Needs PLC on network |
| Ralph Loop | `ralph --monitor` (globally installed) | ✅ Working |
| Ralph Setup | `ralph-setup <project>` | ✅ Working |

### Edge Devices

| What | Command | Status |
|------|---------|--------|
| Pi Edge Server | `sudo python edge_server.py` (in `services/plc-modbus/factorylm-edge/`) | ⚠️ Needs Raspberry Pi |

### Tests

| What | Command | Count |
|------|---------|-------|
| core/ tests | `cd core && pytest` | 148 |
| My-Ralph tests | `cd My-Ralph && npm test` | 321 |
| plc-client tests | `cd plc-client && pytest` | ? |
| plc-client-factoryio tests | `cd plc-client-factoryio && pytest` | ? |

---

## External Services & Dependencies

| Service | Used By | Purpose |
|---------|---------|---------|
| **Groq** | `core/`, OpenClaw bots | LLM provider (free tier, llama-3.3-70b) |
| **Anthropic (Claude)** | `core/`, OpenClaw bots | LLM provider (Max subscription + API key) |
| **DeepSeek** | `core/` | LLM provider |
| **Google Gemini** | `services/plc-copilot/` | Vision AI for equipment photo ID |
| **Telegram** | `services/plc-copilot/`, OpenClaw | Bot interface |
| **Atlas CMMS** | `services/plc-copilot/` | Work order + asset management API |
| **Axiom** | OpenClaw bots (VPS) | Log aggregation (Vector shippers) |
| **Honeycomb** | OpenClaw bots (all instances) | Distributed tracing (OTel SDK) |
| **GitHub Actions** | `My-Ralph/` | CI/CD for tests |
| **Turborepo** | Root monorepo | Build orchestration (mostly unused) |
| **pymodbus** | `services/plc-modbus/`, `plc-client*` | Modbus TCP communication |
| **Neon PostgreSQL** | `My-Ralph/` (MCP) | Serverless Postgres |
| **Supabase** | `My-Ralph/` (MCP) | Backend-as-a-service |

---

## PLC Client — Single Source of Truth

**Canonical location:** `services/plc-modbus/src/factorylm_plc/`

Two earlier iterations exist but are **deprecated** (see `DEPRECATED.md` in each):

| Directory | Status | Why deprecated |
|-----------|--------|---------------|
| `plc-client/` | ⛔ **DEPRECATED (V1)** | Older subdirectory structure, missing modules, uses deprecated `slave=` pymodbus API |
| `plc-client-factoryio/` | ⛔ **DEPRECATED (V2)** | Near-identical to V3 but missing `llm4plc.py`, uses deprecated `slave=` API |
| `services/plc-modbus/src/factorylm_plc/` | ✅ **CANONICAL (V3)** | Most complete, modern pymodbus `device_id=`, LLM integration, active consumers |

**Follow-up:** Migrate any useful tests from V1/V2 into `services/plc-modbus/`, then delete the deprecated directories entirely.

---

## Placeholder Directories (Clearly Marked)

These exist in the Turborepo workspace as aspirational placeholders. Each now has a `NOT_IMPLEMENTED.md` file so no one (human or AI) mistakes them for real code:

| Directory | Intended Purpose | Status |
|-----------|-----------------|--------|
| `apps/dashboard/` | Unified analytics dashboard | ⏸️ Not implemented |
| `apps/web/` | Web frontend | ⏸️ Not implemented |
| `services/api/` | Shared API gateway | ⏸️ Not implemented |
| `services/assistant/` | Customer-facing AI assistant | ⏸️ Not implemented |
| `packages/auth/` | Shared authentication | ⏸️ Not implemented |
| `packages/db/` | Shared DB schemas/migrations | ⏸️ Not implemented |
| `packages/ui/` | Shared React components | ⏸️ Not implemented |

Additionally, `core/` has empty Python stub directories (`adapters/`, `services/`, `models/`, `i18n/`) with only `__init__.py` — these are part of the core package structure and are fine to leave.

---

## Config Defaults (Updated)

`core/src/factorylm/config.py` now has current model defaults with inline comments:

| Provider | Default Model | Notes |
|----------|--------------|-------|
| `groq` | `llama-3.3-70b-versatile` | Free tier, primary across all bots |
| `deepseek` | `deepseek-chat` | Budget fallback |
| `claude` | `claude-sonnet-4-20250514` | Best reasoning, needs API key or Max sub |
| `flm` | `flm-industrial-v1` | Future — not yet available |

---

---

## Refactors Completed

### A. PLC Client Deduplication (2026-02-12)

**What was wrong:** Three copies of `factorylm_plc/` existed — `plc-client/` (V1), `plc-client-factoryio/` (V2), and `services/plc-modbus/` (V3). V2 and V3 shared 7 identical files. V1 was a completely different structure.

**What changed:**
- Designated `services/plc-modbus/src/factorylm_plc/` as the single canonical source
- Added `DEPRECATED.md` to `plc-client/` and `plc-client-factoryio/` marking them superseded
- Updated this document to reflect the new canonical location

**Follow-up:** Migrate useful tests from V1/V2, then delete the deprecated directories.

### B. Placeholder Directories Marked (2026-02-12)

**What was wrong:** 7 directories in the Turborepo workspace contained only a generic README or nothing at all. Tools and AI agents treated them as real components, wasting time investigating them.

**What changed:**
- Added `NOT_IMPLEMENTED.md` to all 7 placeholder directories with clear "this doesn't exist yet" messaging
- Each file includes the intended purpose and a checklist so future work can track progress
- Original READMEs preserved (they may contain useful context)
- Updated this document with a clean table of what's real vs. aspirational

**Follow-up:** When any of these components actually get built, replace `NOT_IMPLEMENTED.md` with a proper README.

### C. Stale Model Defaults Fixed (2026-02-12)

**What was wrong:** `core/src/factorylm/config.py` had model defaults from early 2024 that didn't match what we actually use: `mixtral-8x7b-32768` (Groq) and `claude-3-sonnet-20240229` (Anthropic).

**What changed:**
- Updated Groq default: `mixtral-8x7b-32768` → `llama-3.3-70b-versatile`
- Updated Claude default: `claude-3-sonnet-20240229` → `claude-sonnet-4-20250514`
- Added plain-English comments to every config field and provider so a non-developer can understand what each setting does
- Added links to each provider's console for getting API keys

**Follow-up:** None — this is complete. Keep defaults in sync when switching models in the future.

---

### D. Offline-First Migration Plan (2026-02-13)

**What's happening:** Moving from 3 VPSes (DigitalOcean, Hostinger, Hetzner) to an offline-first setup where everything runs locally and only one minimal VPS (Hetzner) handles public web traffic.

**New docs created:**
- `infra/migration/vps_inventory.md` — Every VPS, its services, data paths, and migration priority
- `infra/migration/target_architecture.md` — End-state diagram (local everything, Hetzner = Caddy only)
- `infra/migration/progress.md` — Checklist with hour estimates (~17h total)
- `infra/migration/hostinger.md` — Extraction runbook for Hostinger (jarvis-legacy)
- `infra/migration/digitalocean.md` — Extraction runbook for DigitalOcean (ultron)
- `infra/migration/hetzner_minimal.md` — Setup guide for minimal Hetzner (Caddy + Tailscale)
- `docs/local_setup.md` — Full local dev setup instructions
- `docs/infra_overview.md` — Script and infrastructure tool inventory

**Follow-up:** Execute extraction runbooks, build Docker Compose, decommission old VPSes.

---

*This document will be updated as cleanup progresses through Phases 2-5.*
