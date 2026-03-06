# OUTCOMES.md — Mikecranesync Repos by What They DO

> Generated: 2026-03-06 | Enriched with tier-1 deep maps
> Total repos: 86 (4 tier-1, 44 tier-2, 38 tier-3)

This groups every repo by **outcome** — what it actually does for Mike,
not what it's named or where it lives. Repos appear in multiple groups
if they serve multiple outcomes.

---

## Diagnose PLC / Factory Faults

_Software that helps identify, analyze, or fix problems with industrial equipment_

**Key overlap:** `factorylm`, `pi-factory-cosmos`, and `factorylm-cosmos-cookoff` all contain independent `fault_classifier` / `conveyor_faults` modules with similar rule sets (E-stop, overcurrent, overtemp, jam, sensor failure). These should be unified into one canonical fault engine in the monolith.

| Repo | Tier | Language | One-liner | Consolidation |
|------|------|----------|-----------|---------------|
| [factorylm](https://github.com/Mikecranesync/factorylm) | 1 | TS/Python | Industrial AI monolith — 23 services, 39 workers, diagnosis engine | **THE monolith** |
| [pi-factory-cosmos](https://github.com/Mikecranesync/pi-factory-cosmos) | 1 | Python | Pi appliance — 13 fault rules, Cosmos R2, VFD Modbus, belt tachometer | Partial merge candidate |
| [factorylm-cosmos-cookoff](https://github.com/Mikecranesync/factorylm-cosmos-cookoff) | 1 | Python | Cookoff entry — edge gateway, 30+ endpoints, matrix dashboard, speed fusion | Partial merge candidate |
| [openclaw](https://github.com/Mikecranesync/openclaw) | 2 | Python | Intent-aware LLM routing for factory diagnostics | Embedded copy in monolith |
| [JarvisTLaptop](https://github.com/Mikecranesync/JarvisTLaptop) | 2 | Python | Telegram bot — photo diagnosis, voice transcription | Overlaps monolith telegram service |
| [factorylm-plc-client](https://github.com/Mikecranesync/factorylm-plc-client) [MERGED] | 2 | Python | Merged into monolith `plc-client/` | Done |
| [factorylm-conveyor-demo](https://github.com/Mikecranesync/factorylm-conveyor-demo) | 2 | D2 | Mechanical drawings, schematics, BOM for conveyor | Standalone (docs) |
| [voltron](https://github.com/Mikecranesync/voltron) | 2 | Python | Distributed edge gateways + Matrix controller | Superseded by cookoff |
| [JARVIS-IS-DEAD](https://github.com/Mikecranesync/JARVIS-IS-DEAD) | 2 | Python | Frozen OpenClaw backup — resurrection kit | Standalone (insurance) |

## Route Messages to AI

_Gateways and bots that accept human input and route it to the right AI model_

**Key overlap:** `openclaw` exists as both a standalone repo and embedded in the monolith (`openclaw/`). The monolith also has `services/llm-router/` which does similar routing. `clawdbot`, `jarvis-core`, `jarvis-unified` are all personal AI assistants with message routing.

| Repo | Tier | Language | One-liner | Consolidation |
|------|------|----------|-----------|---------------|
| [openclaw](https://github.com/Mikecranesync/openclaw) | 2 | Python | Industrial LLM gateway — Groq, Claude, Gemini. Telegram, WhatsApp, HTTP | VPS deployment (standalone) |
| [clawdbot](https://github.com/Mikecranesync/clawdbot) | 2 | TypeScript | Personal AI assistant — 4,433 files | Standalone |
| [jarvis-core](https://github.com/Mikecranesync/jarvis-core) | 2 | TypeScript | JARVIS OS — orchestrates 10+ AI apps | Superseded by jarvis-unified? |
| [jarvis-unified](https://github.com/Mikecranesync/jarvis-unified) | 2 | TypeScript | JARVIS Unified — Email, Calendar, Tasks with 70% test coverage | Latest Jarvis iteration |

## Manage Maintenance (CMMS)

_Track work orders, assets, maintenance schedules_

**Key overlap:** `cmms` is an upstream fork (1,831 files), `factorylm-cmms` is a GitHub-native Issues-based approach, and 5 archived Nexus repos are all abandoned predecessors. The monolith embeds the cmms fork at `apps/cmms/`.

| Repo | Tier | Language | One-liner | Consolidation |
|------|------|----------|-----------|---------------|
| [cmms](https://github.com/Mikecranesync/cmms) | 2 | TypeScript | Upstream CMMS fork — 1,831 files, full web+mobile | Embedded in monolith |
| [factorylm-cmms](https://github.com/Mikecranesync/factorylm-cmms) | 2 | — | ISO 55000 GitHub-native CMMS using Issues | Standalone (different approach) |
| [nexus-cmms-recovery-point-2](https://github.com/Mikecranesync/nexus-cmms-recovery-point-2) [ARCHIVED] | 3 | TypeScript | Abandoned Nexus recovery | Deprecated |
| [ProjectNexus](https://github.com/Mikecranesync/ProjectNexus) [ARCHIVED] | 3 | TypeScript | Abandoned Nexus web | Deprecated |
| [Nexus](https://github.com/Mikecranesync/Nexus) [ARCHIVED] | 3 | Dart | Abandoned Nexus mobile | Deprecated |
| [Nexus1](https://github.com/Mikecranesync/Nexus1) [ARCHIVED] | 3 | — | Abandoned | Deprecated |
| [Nexus-backend](https://github.com/Mikecranesync/Nexus-backend) [ARCHIVED] | 3 | — | Abandoned meter app | Deprecated |

## Train Technicians

_Gamified learning for industrial maintenance skills_

| Repo | Tier | Language | One-liner | Consolidation |
|------|------|----------|-----------|---------------|
| [IndustrialSkillsHub](https://github.com/Mikecranesync/IndustrialSkillsHub) | 2 | TypeScript | Duolingo-style web app for maintenance training | Standalone |
| [IndustrialSkillsHub-native](https://github.com/Mikecranesync/IndustrialSkillsHub-native) | 2 | TypeScript | React Native mobile app for same | Standalone |

## Automate Email / Calendar

_AI-powered email triage, drafting, and calendar management_

| Repo | Tier | Language | One-liner | Consolidation |
|------|------|----------|-----------|---------------|
| [jarvis-for-gmail](https://github.com/Mikecranesync/jarvis-for-gmail) | 2 | TypeScript | Autonomous email assistant — handles 70% automatically | Standalone |
| [jarvis-unified](https://github.com/Mikecranesync/jarvis-unified) | 2 | TypeScript | PAI OS — Email + Calendar + Tasks automation | Standalone |
| [jarvis-android-voice-proto](https://github.com/Mikecranesync/jarvis-android-voice-proto) | 2 | PowerShell | Voice-controlled email for Android | Prototype |

## Control PLC Hardware

_Direct communication with Micro820, Modbus devices, VFDs_

**Key overlap:** The monolith has `services/plc-modbus/` (21 files). `pi-factory-cosmos` has its own `VFDReader` class. `factorylm-cosmos-cookoff` has `net/micro820.py` (deprecated) + async scanner. Three independent Modbus implementations.

| Repo | Tier | Language | One-liner | Consolidation |
|------|------|----------|-----------|---------------|
| [factorylm](https://github.com/Mikecranesync/factorylm) | 1 | TS/Python | Monolith `services/plc-modbus/` — canonical PLC client | **THE source** |
| [pi-factory-cosmos](https://github.com/Mikecranesync/pi-factory-cosmos) | 1 | Python | VFDReader + PLCSimulator (standalone, edge) | Edge-specific |
| [factorylm-cosmos-cookoff](https://github.com/Mikecranesync/factorylm-cosmos-cookoff) | 1 | Python | Edge gateway with async subnet scanner | Superset of pi-factory |
| [factorylm-plc-client](https://github.com/Mikecranesync/factorylm-plc-client) [MERGED] | 2 | Python | Merged into monolith | Done |
| [factorylm-mini](https://github.com/Mikecranesync/factorylm-mini) [MERGED] | 2 | C++ | Merged into monolith | Done |
| [pi-gateway](https://github.com/Mikecranesync/pi-gateway) [MERGED] | 2 | Python | Merged into monolith | Done |
| [ModbusTools](https://github.com/Mikecranesync/ModbusTools) [FORK] | 3 | C++ | Modbus simulator GUI | Reference fork |
| [modbus-simulator](https://github.com/Mikecranesync/modbus-simulator) [FORK] | 3 | Python | Modbus simulator + kivy GUI | Reference fork |
| [motulator](https://github.com/Mikecranesync/motulator) [FORK] | 3 | Python | Motor drive simulator | Embedded in monolith `simulation/` |

## Collect & Analyze Sensor Data

_Time-series collection, drift detection, anomaly analysis_

| Repo | Tier | Language | One-liner | Consolidation |
|------|------|----------|-----------|---------------|
| [factorylm](https://github.com/Mikecranesync/factorylm) | 1 | TS/Python | Monolith `analytics/` + `collectors/` — baseline, drift, embedding | **THE source** |
| [pi-factory-cosmos](https://github.com/Mikecranesync/pi-factory-cosmos) | 1 | Python | Belt tachometer — vision-based RPM from orange tape tracking | Edge-specific |
| [factorylm-cosmos-cookoff](https://github.com/Mikecranesync/factorylm-cosmos-cookoff) | 1 | Python | 5Hz poller with SQLite history, speed fusion detection | Edge-specific |

## Manage Network Infrastructure

_Cluster topology, device health, IPAM_

| Repo | Tier | Language | One-liner | Consolidation |
|------|------|----------|-----------|---------------|
| [nautobot-docker-compose](https://github.com/Mikecranesync/nautobot-docker-compose) | 1 | Python | Nautobot fork + 6 custom tools — topology seeder, health monitor, endpoint scanner | Standalone |

## AI Agent Orchestration

_Autonomous dev loops, agent frameworks, task management_

| Repo | Tier | Language | One-liner | Consolidation |
|------|------|----------|-----------|---------------|
| [ralph](https://github.com/Mikecranesync/ralph) | 2 | TypeScript | Autonomous PRD completion loop | Standalone |
| [My-Ralph](https://github.com/Mikecranesync/My-Ralph) | 2 | Shell | Claude Code auto-loop with exit detection | Standalone |
| [CodeBang](https://github.com/Mikecranesync/CodeBang) | 2 | Python | Self-improving DevCTO agent | Standalone |
| [Archon](https://github.com/Mikecranesync/Archon) | 2 | Python | Knowledge + task management for AI agents | Standalone |
| [Agent-Factory](https://github.com/Mikecranesync/Agent-Factory) | 2 | Python | Specialized agent framework with dynamic tools | Standalone |
| [master-of-puppets-v2](https://github.com/Mikecranesync/master-of-puppets-v2) | 2 | Python | Recursive self-improving code intelligence | Standalone |
| [Backlog.md](https://github.com/Mikecranesync/Backlog.md) | 2 | TypeScript | Git-native backlog for human+AI collaboration | Standalone |
| [antfarm](https://github.com/Mikecranesync/antfarm) [FORK] | 3 | TypeScript | Multi-agent workflows for OpenClaw | Reference fork |

## Personal AI Infrastructure

_PAI config, workspace setup, cross-device AI assistants_

| Repo | Tier | Language | One-liner | Consolidation |
|------|------|----------|-----------|---------------|
| [jarvis-workspace](https://github.com/Mikecranesync/jarvis-workspace) | 2 | Python | Clawdbot workspace config — 5,664 files | Standalone |
| [pai-config-windows](https://github.com/Mikecranesync/pai-config-windows) | 2 | JavaScript | Windows PowerShell PAI config with hooks/skills | Standalone |
| [Thefuture](https://github.com/Mikecranesync/Thefuture) | 2 | TypeScript | PAI for upgrading humans — 605 files | Standalone |
| [remoteme-jarvis-node](https://github.com/Mikecranesync/remoteme-jarvis-node) | 2 | Python | FastAPI MCP server for remote laptop control | Standalone |
| [clawd](https://github.com/Mikecranesync/clawd) | 2 | Shell | Claude Code agent config/scripts | Standalone |
| [claudegen-coach](https://github.com/Mikecranesync/claudegen-coach) | 2 | TypeScript | AI coaching/generation tool | Standalone |

## Vision / Inspection

_Computer vision for industrial inspection and diagnostics_

**Key overlap:** `pi-factory-cosmos` has `BeltTachometer` (297 lines, HSV orange mask). `factorylm-cosmos-cookoff` has the same tachometer plus `cosmos_analyzer.py` for video reasoning. Both repos contain near-identical `frame_capture.py`.

| Repo | Tier | Language | One-liner | Consolidation |
|------|------|----------|-----------|---------------|
| [pi-factory-cosmos](https://github.com/Mikecranesync/pi-factory-cosmos) | 1 | Python | Belt tachometer + Cosmos R2 video diagnosis | Edge-specific |
| [factorylm-cosmos-cookoff](https://github.com/Mikecranesync/factorylm-cosmos-cookoff) | 1 | Python | Same + speed fusion, incident watcher, 6 demo subcommands | Superset |
| [RideView](https://github.com/Mikecranesync/RideView) | 2 | Python | Torque stripe verification — bolt inspection CV | Standalone |
| [frame_realtime_gemini_voicevision](https://github.com/Mikecranesync/frame_realtime_gemini_voicevision) | 2 | Dart | Brilliant Labs Frame + Gemini realtime | Standalone |

## Knowledge Base / Memory

_Obsidian vaults, vector stores, persistent agent memory_

| Repo | Tier | Language | One-liner | Consolidation |
|------|------|----------|-----------|---------------|
| [FactoryLM_OS](https://github.com/Mikecranesync/FactoryLM_OS) | 2 | — | Obsidian vault — 435 files, operating brain | Standalone |
| [factorylm-agent-space](https://github.com/Mikecranesync/factorylm-agent-space) | 2 | — | Obsidian agent space — 3,410 files | Standalone |
| [mikes-brain](https://github.com/Mikecranesync/mikes-brain) [MERGED] | 2 | Python | Merged into monolith `brain/` | Done |

## Frontend / Landing Pages

_Marketing sites, UI libraries, component forks_

| Repo | Tier | Language | One-liner | Consolidation |
|------|------|----------|-----------|---------------|
| [factorylm-landing](https://github.com/Mikecranesync/factorylm-landing) | 2 | HTML | factorylm.com landing page | Standalone |
| [plc-copilot-landing](https://github.com/Mikecranesync/plc-copilot-landing) | 2 | TypeScript | PLC Copilot landing page | Standalone |
| [tailwindcss](https://github.com/Mikecranesync/tailwindcss) [FORK] | 3 | TypeScript | CSS framework | Reference |
| [ui](https://github.com/Mikecranesync/ui) [FORK] | 3 | TypeScript | shadcn/ui components | Reference |
| [magicui](https://github.com/Mikecranesync/magicui) [FORK] | 3 | MDX | Animated components | Reference |
| [daisyui](https://github.com/Mikecranesync/daisyui) [FORK] | 3 | Svelte | Tailwind component library | Reference |
| [motion](https://github.com/Mikecranesync/motion) [FORK] | 3 | TypeScript | Framer Motion | Reference |
| [primitives](https://github.com/Mikecranesync/primitives) [FORK] | 3 | TypeScript | Radix primitives | Reference |
| [spectrum-ui](https://github.com/Mikecranesync/spectrum-ui) [FORK] | 3 | TypeScript | Spectrum UI components | Reference |
| [svelte-animations](https://github.com/Mikecranesync/svelte-animations) [FORK] | 3 | Svelte | Svelte animation components | Reference |
| [galaxy](https://github.com/Mikecranesync/galaxy) [FORK] | 3 | HTML | Open-source UI library | Reference |
| [saasternity](https://github.com/Mikecranesync/saasternity) [FORK] | 3 | TypeScript | SaaS boilerplate | Reference |
| [tailwind-landing-page-template](https://github.com/Mikecranesync/tailwind-landing-page-template) [FORK] | 3 | TypeScript | Landing page template | Reference |

## Blogging / Content

_AI-powered content generation_

| Repo | Tier | Language | One-liner | Consolidation |
|------|------|----------|-----------|---------------|
| [Blog-writer-multi-agent](https://github.com/Mikecranesync/Blog-writer-multi-agent) | 2 | Jupyter Notebook | Multi-agent blog writer with LangChain + Gemini | Standalone |

## Abandoned / Archived Experiments

_Past experiments, superseded projects — no action needed_

| Repo | Tier | Language | One-liner |
|------|------|----------|-----------|
| [Chucky](https://github.com/Mikecranesync/Chucky) [ARCHIVED] | 3 | HTML | AI App |
| [chucky_project](https://github.com/Mikecranesync/chucky_project) [ARCHIVED] | 3 | PLpgSQL | Database-backed project |
| [Friday](https://github.com/Mikecranesync/Friday) [ARCHIVED] | 3 | TypeScript | Personal project |
| [Friday-2](https://github.com/Mikecranesync/Friday-2) [ARCHIVED] | 3 | TypeScript | AI studio friday v2 |
| [FRIDAYNEW](https://github.com/Mikecranesync/FRIDAYNEW) [ARCHIVED] | 3 | TypeScript | AI studio friday v3 |
| [Einstein](https://github.com/Mikecranesync/Einstein) [ARCHIVED] | 3 | — | App |
| [your-assistant-app](https://github.com/Mikecranesync/your-assistant-app) [ARCHIVED] | 3 | — | Assistant app |
| [questify-kid-learn](https://github.com/Mikecranesync/questify-kid-learn) [ARCHIVED] | 3 | TypeScript | Kids learning app |
| [VibeBuddy](https://github.com/Mikecranesync/VibeBuddy) [ARCHIVED] | 3 | — | Vibe app |
| [TechMeterAI](https://github.com/Mikecranesync/TechMeterAI) [ARCHIVED] | 3 | — | Meter app |
| [ScoutPathApp](https://github.com/Mikecranesync/ScoutPathApp) [ARCHIVED] | 3 | HTML | Scout path app |
| [AISmartMeterApp](https://github.com/Mikecranesync/AISmartMeterApp) [ARCHIVED] | 3 | — | Smart meter app |
| [langchain-crash-course](https://github.com/Mikecranesync/langchain-crash-course) [ARCHIVED] | 3 | Python | LangChain tutorial |

## Uncategorized

_Repos not fitting cleanly into an outcome group_

| Repo | Tier | Language | One-liner | Notes |
|------|------|----------|-----------|-------|
| [default](https://github.com/Mikecranesync/default) | 2 | — | Shared Ranger config | Org config |
| [factorylm-core](https://github.com/Mikecranesync/factorylm-core) [MERGED] | 2 | Python | Merged into monolith `core/` | Done |
| [mikecranesync](https://github.com/Mikecranesync/mikecranesync) | 2 | — | GitHub profile README | Profile |
| [openclaw-workspace](https://github.com/Mikecranesync/openclaw-workspace) | 2 | Python | OpenClaw dev workspace config | Config |
| [resurrected-tools](https://github.com/Mikecranesync/resurrected-tools) | 2 | TypeScript | Revived tools from abandoned repos | Utility |
| [Rivet-PRO](https://github.com/Mikecranesync/Rivet-PRO) | 2 | Python | V2.0 — unclear purpose, 1,145 files | Needs review |
| [cal.com](https://github.com/Mikecranesync/cal.com) [FORK] | 3 | TypeScript | Scheduling infrastructure | Reference |
| [exo](https://github.com/Mikecranesync/exo) [FORK] | 3 | Python | Run frontier AI locally | Reference |
| [n8n-docs](https://github.com/Mikecranesync/n8n-docs) [FORK] | 3 | HTML | n8n automation docs | Reference |
| [RealtimeSTT](https://github.com/Mikecranesync/RealtimeSTT) [FORK] | 3 | Python | Speech-to-text library | Reference |
| [VideoAgent](https://github.com/Mikecranesync/VideoAgent) [FORK] | 3 | Python | Video understanding framework | Reference |

---

## Consolidation Summary

### High-Priority Merges

| What | From | Into | Why |
|------|------|------|-----|
| Fault classifier rules | pi-factory-cosmos, cookoff | factorylm `diagnosis/` | 3 independent copies of same fault rules |
| VFD reader | pi-factory-cosmos | factorylm `services/plc-modbus/` | Duplicate Modbus client |
| Belt tachometer | pi-factory-cosmos, cookoff | factorylm `cosmos/` | Vision tachometer exists in 2 repos |
| Frame capture | pi-factory-cosmos, cookoff | factorylm `cosmos/` | Near-identical OpenCV module |

### Already Merged (5 repos)

`factorylm-core` -> `core/`, `factorylm-plc-client` -> `plc-client/`, `factorylm-mini` -> `gateway/`, `mikes-brain` -> `brain/`, `pi-gateway` -> `gateway/`

### Keep Standalone

- **openclaw** — deployed on VPS, separate lifecycle
- **IndustrialSkillsHub** (web + native) — separate product
- **nautobot-docker-compose** — infrastructure tool
- **Jarvis repos** (unified, for-gmail, core) — personal AI, different domain
- **Agent orchestration repos** — experimental, different audiences
- **Obsidian vaults** (FactoryLM_OS, agent-space) — knowledge, not code
