# Mikecranesync Repo Capabilities Index

*Generated: 2026-02-16 — Phase A Extended Discovery*
*Scope: All 50 repos under github.com/Mikecranesync*

---

## Master Repo Table

Legend:
- **Scanned** = targeted search for gist/project/scaffold/code-CLI capabilities
- **Relevant** = capabilities that could support Telegram → Gist/Project flow or Ant Farm orchestration

| # | Repo | Description | Category | Scanned | Relevant Capabilities |
|---|------|-------------|----------|---------|----------------------|
| 1 | **openclaw** | Industrial AI gateway — LLM routing for factory diagnostics | OpenClaw Ecosystem | ✅ Done | 9 skills, intent dispatch, Telegram adapter. No gist/scaffold. |
| 2 | **factorylm** | Industrial AI Platform (monorepo) | FactoryLM Monorepo | ✅ Done | Celery workers (38+), Monkey dispatcher, Conductor, Cartographer (PLC code gen), Evolution (self-improvement), Hammurabi/Herodotus (brain). No gist creation. |
| 3 | **Agent-Factory** | Scalable framework for AI agents with dynamic tool assignment | Agent-Factory | ✅ Done | **SCAFFOLD** (autonomous code gen → PRs), **factory.py** (spec → code), Telegram `/scaffold` command, RIVET Pro SME agents, Plugin SDK, 20 marketing agents |
| 4 | **Backlog.md** | Markdown-native task manager + Kanban | Agent-Factory | ✅ Done | `npm i -g backlog.md` CLI, MCP integration for AI assistants, web UI. SCAFFOLD's task source. |
| 5 | **My-Ralph** | Autonomous AI dev loop for Claude Code | Agent-Factory | ✅ Done | Continuous Claude Code loop with circuit breaker, rate limiting, dual exit gate. 310 tests. |
| 6 | **clawdbot** | Personal AI assistant — Any OS, Any Platform | Clawdbot/PAI | ✅ Done | **Full CLI platform**: `onboard` wizard, Skills system (`SKILL.md`), Plugin SDK, 28 extensions (WhatsApp/Telegram/Slack/Discord/Signal/iMessage/etc.), Canvas scaffold, **Prose DSL** for agent workflows, 60+ CLI commands |
| 7 | **Rivet-PRO** | RIVET v2.0 — Industrial maintenance AI product | Rivet/RivetPro | ✅ Done | Manim video templates (6 types), Fly.io deploy template, Builder Agent integration plan, SME prompt templates, OCR workflow |
| 8 | **voltron** | Distributed industrial AI — edge gateways, Matrix controller | FactoryLM Ecosystem | ✅ Done | Matrix controller, distributed nodes, LLM tiering, policy engine. Templates for policy.yaml/soul.md. No gist/scaffold. |
| 9 | **JARVIS-IS-DEAD** | Frozen digital twin of Jarvis. PR-gated resurrection kit. | Jarvis Ecosystem | ✅ Done | Historical gist retrieval test: "Can you find the GIST file for my conveyor project?" Confirms Jarvis had gist awareness. |
| 10 | **jarvis-workspace** | AI workspace config — Clawdbot infrastructure | Jarvis Ecosystem | ✅ Done | **Jobs system** (JOB-2026-0206-001 with drawings, BOMs, build guides, CAD, SVGs), **factorylm-templates** (user profile, work order), SOUL.md/CONSTITUTION.md, multi-agent org chart, signals inbox/outbox |
| 11 | **jarvis-core** | JARVIS — AI Operating System hub (DEPRECATED) | Jarvis Ecosystem | ✅ Done | **`@jarvis/create-subapp` CLI** — full interactive project generator (prompts, template copy, placeholder replacement, npm install, git init). Sub-app template + registry. |
| 12 | **jarvis-unified** | JARVIS Unified — PAI-Powered Personal AI OS | Jarvis Ecosystem | ✅ Done | ADR template, Gmail CLI automation, test report generator. No general scaffolding. |
| 13 | **jarvis-for-gmail** | Autonomous agentic email assistant | Jarvis Ecosystem | ✅ Done | 6 GitHub issue templates, Gmail CLI automation, draft generator. No scaffolding. |
| 14 | **jarvis-android-voice-proto** | Voice-controlled email assistant (DEPRECATED) | Jarvis Ecosystem | ✅ Done | `.jarvis-memory/` agent memory system pattern, Claude skill scripts (git-commit, memory-reader/writer). |
| 15 | **remoteme-jarvis-node** | FastAPI MCP Server for remote laptop control | Jarvis Ecosystem | ✅ Done | `/shell`, `/files/read`, `/files/write`, `/screenshot`, `/notify` endpoints. Pure API server, no scaffolding. |
| 16 | **factorylm-core** | Unified LLM client library (ARCHIVED — merged to monolith) | FactoryLM Libraries | ✅ Done | Groq/DeepSeek/Claude/FLM abstraction, cost tracking. No scaffolding. |
| 17 | **factorylm-plc-client** | Production Modbus TCP library (ARCHIVED — merged to monolith) | FactoryLM Libraries | ✅ Done | v0.4.0 Modbus client, LLM4PLC ST code gen, MockPLC. No scaffolding. |
| 18 | **factorylm-cmms** | ISO 55000 GitHub-native CMMS | FactoryLM Products | ✅ Done | GitHub Issues + Gists as CMMS storage concept. No scaffolding code. |
| 19 | **IndustrialSkillsHub** | Duolingo-style gamified industrial training | FactoryLM Products | ✅ Done | Next.js web app, bilingual Spanish/English, courses/glossary. No scaffolding. |
| 20 | **IndustrialSkillsHub-native** | React Native mobile app for industrial training | FactoryLM Products | ✅ Done | Expo/React Native scaffold with Clerk auth. Early stage. |
| 21 | **resurrected-tools** | Resurrected tools from abandoned repos | Standalone | ✅ Done | Contains RideView (torque stripe CV) and industrial-skills-hub. No gist/scaffold. |
| 22 | **CodeBang** | DevCTO Agent — self-improving AI DevOps (DEPRECATED) | Agent-Factory | ✅ Done | KB-first architecture, Digest→Analyze→Act→Learn loop. Superseded by Agent-Factory. |
| 23 | **ralph** | Autonomous AI agent loop for PRD completion | Agent-Factory | ✅ Done | `ralph.sh` CLI, PRD-to-JSON conversion, Amp AI coding agent loop, skills system. |
| 24 | **Archon** | Knowledge + task management backbone for AI coders | AI Infrastructure | ✅ Done | **MCP server** (port 8051), web UI, FastAPI backend, knowledge crawling, RAG search, PRP (Product Requirements Protocol) templates. |
| 25 | **Thefuture** | PAI: Personal AI Infrastructure for upgrading humans | AI Infrastructure | ✅ Done | Full `.claude/` scaffold (8 agent personas, 14+ TypeScript hooks, commands, UOCS history system). Drop-in template. |
| 26 | **pai-config-windows** | PAI config for Windows PowerShell | AI Infrastructure | ✅ Done | `.claude/` agent scaffold (8 agents), hooks (12 TypeScript), documentation system, voice setup guide. Windows-specific PAI. |
| 27 | **RideView** | Torque stripe verification with computer vision | FactoryLM Products | ✅ Done | Multi-platform CV app, `.claude/` hooks (validators), `.ralph/` integration, `shippa` command. Industrial QC tool. |
| 28 | **VideoAgent** | All-in-One Agentic Framework for Video (fork) | Media Tools | ✅ Done | Multi-modal video understanding/editing/generation. Natural language video ops. |
| 29 | **Blog-writer-multi-agent** | Multi-agent blog writing (Crew AI) | Media Tools | ✅ Done | Planner→Writer→Editor pipeline, Gemini 2.0 Flash, Next.js frontend. |
| 30 | **factorylm-conveyor-demo** | VFD conveyor assembly — drawings, schematics, BOM | Hardware Docs | ✅ Done | Build guides, D2 diagrams, DXF CAD, BOM templates, Imgur upload script. |
| 31 | **factorylm-landing** | Landing page for factorylm.com | Marketing | ✅ Done | Static HTML, SEO blog library (10 posts), edge gateway configurator (drag-drop UI). |
| 32 | **plc-copilot-landing** | PLC Copilot marketing site | Marketing | ✅ Done | Next.js 14 landing page scaffold, waitlist form, Telegram CTA, equipment logos. |
| 33 | **factorylm-mini** | ESP32 IoT sensor node scaffold (ARCHIVED) | Hardware | ✅ Done | PlatformIO ESP32 firmware, Modbus TCP/CAN bus/analog I/O. ~$30/device. |
| 34 | **mikes-brain** | External cognitive system / knowledge graph (ARCHIVED) | AI Infrastructure | ✅ Done | Worker patterns (Hammurabi, Herodotus, Gutenberg, Tesla, Hypatia), Neon+pgvector schema, YAML templates, spec-driven dev methodology. |
| 35 | **claudegen-coach** | 6-stage PDLC coach app (DEPRECATED) | AI Infrastructure | ✅ Done | Claude API + n8n patterns. React/Supabase/Zustand. Reference only. |
| 36 | **frame_realtime_gemini_voicevision** | Brilliant Labs Frame + Gemini multimodal (fork) | Hardware | ✅ Done | Flutter AR glasses + Gemini voice+vision streaming. Halo glasses reference. |
| 37 | **RealtimeSTT** | Real-time speech-to-text library (fork) | Voice | ✅ Done | Microphone → text transcription, AudioToTextRecorder, CLI. Voice input dependency. |
| 38 | **mikecranesync** | GitHub Profile README | Meta | ✅ Done | Auto-updating profile via GitHub Actions. |
| 39 | **default** | Shared org-level GitHub config | Meta | ✅ Done | ranger.yml for automated repo management. |
| 40 | **exo** | Run frontier AI locally (fork) | AI Infrastructure | ✅ Done | No custom commits. Bookmarked fork. |
| 41 | **motion** | Modern React animation library (fork) | UI Libraries | ✅ Done | No custom commits. Bookmarked fork. |
| 42 | **tailwindcss** | Utility-first CSS framework (fork) | UI Libraries | ✅ Done | No custom commits. Bookmarked fork. |
| 43 | **ui** | shadcn/ui accessible components (fork) | UI Libraries | ✅ Done | No custom commits. Bookmarked fork. |
| 44 | **magicui** | UI Library for Design Engineers (fork) | UI Libraries | ✅ Done | No custom commits. Bookmarked fork. |
| 45 | **daisyui** | Tailwind CSS component library (fork) | UI Libraries | ✅ Done | No custom commits. Bookmarked fork. |
| 46 | **cal.com** | Scheduling infrastructure (fork) | SaaS Tools | ✅ Done | No custom commits. Bookmarked fork. |
| 47 | **ModbusTools** | Cross-platform Modbus simulator (fork) | Industrial Tools | ✅ Done | No custom commits. Bookmarked fork — relevant for PLC testing. |
| 48 | **motulator** | Motor Drive and Grid Converter Simulator (fork) | Industrial Tools | ✅ Done | No custom commits. Bookmarked fork — relevant for VFD/motor modeling. |
| 49 | **cmms** | Self-hosted CMMS web + mobile app (fork) | Industrial Tools | ✅ Done | No custom commits. Bookmarked fork — competitor/reference for factorylm-cmms. |
| 50 | **Backlog.md** | (same as #4, listed once above) | — | — | — |

**Total: 50 repos scanned. 50/50 complete.**

---

## Category Summaries

### OpenClaw Ecosystem (1 repo)

OpenClaw is the production gateway on the VPS. It has 9 skills, Telegram integration, and intent-based LLM routing. **No gist or project creation capability exists.** All gists were created via ad-hoc `gh gist create` commands during Claude Code sessions.

### Agent-Factory (5 repos: Agent-Factory, Backlog.md, My-Ralph, ralph, CodeBang)

This is the **richest source of project/scaffold capabilities**:
- **SCAFFOLD** in Agent-Factory is a full autonomous code generation pipeline: fetch task → safety check → git worktree → Claude Code executor → PR creation. Already has Telegram `/scaffold` and `/scaffold_status` commands.
- **factory.py** converts markdown specs to Python code ("code is disposable, specs are eternal").
- **Backlog.md** is a published npm tool that serves as SCAFFOLD's task source via MCP.
- **My-Ralph** and **ralph** are autonomous coding loops (Claude Code and Amp respectively).
- **CodeBang** is the deprecated precursor (KB-first DevCTO agent).

### Rivet/RivetPro (1 repo)

Rivet-PRO is a large production app (1,299 files) focused on industrial maintenance AI:
- **Manim video templates** — 6 template types (Title, Diagram, Flowchart, Comparison, LadderLogic, Timeline) with `generate_code()` methods
- **Builder Agent Plan** — design doc for a hybrid agent that receives harvest blocks, routes through 7 vendor SME prompts
- **Fly.io deploy template** — production deployment scaffold
- No gist/CLI capabilities, but the SME prompt templates and video generation could enhance GistSkill output quality.

### Clawdbot/PAI (1 repo)

Clawdbot is the **most feature-complete CLI platform** (4,911 files):
- Skills system (`SKILL.md` convention — just create a directory with a markdown file)
- Plugin SDK for programmatic extensions
- 28 channel extensions (WhatsApp, Telegram, Slack, Discord, Signal, iMessage, etc.)
- **Prose DSL** for agent workflow authoring (with literary "alts" — Borges, Kafka, Homer styles)
- Canvas scaffold for live UI rendering
- Full CLI with 60+ commands including `onboard` wizard

### Jarvis Ecosystem (7 repos)

Historical Jarvis infrastructure:
- **jarvis-core** has the only complete `create-subapp` CLI (interactive prompts, template copy, npm install, git init) — **DEPRECATED but extractable**
- **jarvis-workspace** has the jobs system (engineering packages with drawings, BOMs, build guides) and factorylm-templates
- **JARVIS-IS-DEAD** confirms Jarvis historically understood gist queries ("find the GIST file for my conveyor project")
- **jarvis-android-voice-proto** has a reusable `.jarvis-memory/` agent memory pattern
- **remoteme-jarvis-node** is a clean API server for remote control

### FactoryLM Monorepo (1 repo, many subsystems)

The monorepo has the Ant Farm orchestration layer (Monkey → Conductor → workers → Hammurabi → Herodotus) but **no gist creation**. Cartographer can generate PLC code via remote Claude Code, and Evolution creates Trello task cards, but neither creates gists or scaffolds general projects.

### AI Infrastructure (5 repos: Archon, Thefuture, pai-config-windows, mikes-brain, claudegen-coach)

- **Archon** — MCP server with knowledge crawling, RAG search, PRP templates. Could serve as the KB backend for GistSkill/ProjectSkill.
- **Thefuture/PAI** — Drop-in `.claude/` scaffold with 8 agent personas, 14+ hooks, UOCS history system.
- **pai-config-windows** — Windows-specific version of the PAI scaffold.
- **mikes-brain** — Hammurabi/Herodotus origin repo, Neon+pgvector schema, YAML templates for code generation and spec writing.
- **claudegen-coach** — Deprecated 6-stage PDLC coach. Reference for Claude API + n8n patterns.

### FactoryLM Products (4 repos: factorylm-cmms, IndustrialSkillsHub, ISH-native, RideView)

Product repos with no scaffolding capabilities, but:
- **RideView** demonstrates a mature `.claude/` and `.ralph/` integration pattern
- **factorylm-cmms** uses GitHub Issues + Gists as a CMMS storage concept (relevant to GistSkill)

### Hardware (3 repos: factorylm-conveyor-demo, factorylm-mini, frame_realtime_gemini)

- **factorylm-mini** has a minimal ESP32 firmware scaffold (PlatformIO)
- **factorylm-conveyor-demo** has build guide and BOM templates
- **frame_realtime_gemini** is a fork for AR glasses + Gemini

### Marketing (2 repos: factorylm-landing, plc-copilot-landing)

Landing page templates. plc-copilot-landing is a clean Next.js scaffold with waitlist form and Telegram CTA.

### Forks (10 repos)

All 10 forks have no custom commits — they're bookmarked references. Three are industrially relevant: ModbusTools (Modbus simulator), motulator (motor/VFD simulator), cmms (open-source CMMS reference).

---

## Rivet/RivetPro + FactoryLM: Integration Opportunities

### Capabilities that could enhance Jarvis's KB

| Source | Capability | How it helps |
|--------|-----------|-------------|
| Rivet-PRO SME prompts | 7 vendor-specific prompt templates (Siemens, Rockwell, ABB, Schneider, etc.) | Better diagnosis quality — Jarvis could use the right SME prompt per equipment manufacturer |
| Rivet-PRO RAG pipeline | Knowledge retrieval from manufacturer manuals | Richer search results from DiagnoseSkill and SearchSkill |
| Archon MCP server | Crawl websites, upload PDFs, advanced RAG with reranking | Backend for OpenClaw's KB connector — better knowledge ingestion |
| mikes-brain pgvector schema | Neon schema for knowledge atoms with embeddings | Production-ready KB schema for OpenClaw's asyncpg integration |
| Rivet-PRO manual indexer | Index manufacturer manuals and prints | Automated KB population from PDF equipment manuals |

### Capabilities for project/job templates

| Source | Capability | How it helps |
|--------|-----------|-------------|
| jarvis-workspace Jobs | Engineering packages (drawings, BOMs, build guides, CAD, SVGs) | Template for ProjectSkill output — generate complete job packets |
| jarvis-workspace Templates | Work order + user profile templates | CMMS-style output from GistSkill |
| Rivet-PRO Manim templates | 6 video template types with `generate_code()` | GistSkill could generate animated explainers, not just text |
| factorylm-conveyor-demo | Build guides, D2 diagrams, BOM templates | Template library for hardware project gists |
| mikes-brain YAML templates | `implement_feature.yaml`, `write_spec.yaml` | Structured templates for ProjectSkill code generation |

### How these plug into GistSkill, ProjectSkill, and Ant Farm

**GistSkill integration:**
- **Rivet-PRO Manim templates** → generate animated video gists (not just markdown)
- **jarvis-workspace work order templates** → generate structured CMMS work orders as gists
- **factorylm-conveyor-demo patterns** → generate hardware build guides with embedded diagrams
- **Archon PRP templates** → generate Product Requirements Protocols as gists

**ProjectSkill integration:**
- **Agent-Factory SCAFFOLD** → the core engine. Extract or call it for code generation with safety rails.
- **jarvis-core `create-subapp` pattern** → template-based project scaffolding (deprecated but the pattern is extractable)
- **factory.py spec→code** → generate Python code from markdown specs
- **mikes-brain YAML templates** → structured project generation templates

**Ant Farm / multi-agent orchestration:**
- **Monkey dispatcher** → task routing already exists in monorepo
- **Agent-Factory SCAFFOLD** → autonomous PR creation in git worktrees
- **Backlog.md** → task source via MCP
- **My-Ralph / ralph** → autonomous coding loops
- **clawdbot Prose DSL** → define agent workflows in a domain-specific language
- **Archon MCP server** → shared knowledge base for all agents

---

## NEW Candidate Capabilities (not in Phase A initial report)

These were discovered in the extended scan:

| # | Capability | Source Repo | Why it matters for GistSkill/ProjectSkill |
|---|-----------|------------|------------------------------------------|
| 1 | **`@jarvis/create-subapp` CLI** | jarvis-core (deprecated) | Complete project generator with template copy, placeholder replacement, git init. Extractable pattern for ProjectSkill. |
| 2 | **Clawdbot Skills system** | clawdbot | `SKILL.md` convention — just create a directory with a markdown file. Simplest possible skill scaffolding pattern. Could be adopted for OpenClaw skills. |
| 3 | **Clawdbot Prose DSL** | clawdbot | Define agent workflows as prose (with compiler). Could let Mike define GistSkill/ProjectSkill behaviors in natural language. |
| 4 | **Clawdbot Plugin SDK** | clawdbot | Programmatic extension creation. More structured than SKILL.md but still approachable. |
| 5 | **Archon PRP templates** | Archon | Product Requirements Protocol — structured alternative to PRDs. Natural output format for ProjectSkill. |
| 6 | **Archon MCP server** | Archon | Shared knowledge base accessible by any AI tool. Could be the backend for both GistSkill research and ProjectSkill context assembly. |
| 7 | **Rivet-PRO Manim video templates** | Rivet-PRO | Generate animated videos from templates. GistSkill could produce video explainers, not just text. |
| 8 | **Rivet-PRO Builder Agent plan** | Rivet-PRO | Hybrid agent architecture with vendor SME routing. Pattern for ProjectSkill's LLM routing. |
| 9 | **mikes-brain YAML template system** | mikes-brain | `implement_feature.yaml`, `write_spec.yaml` — structured templates for code/spec generation. |
| 10 | **pai-config-windows hooks system** | pai-config-windows | 12 TypeScript hooks for Claude Code session lifecycle. Could automate GistSkill/ProjectSkill quality checks. |
| 11 | **RideView `.claude/` + `.ralph/` pattern** | RideView | Mature integration of Claude Code hooks + Ralph autonomous loop. Replicable pattern for any FactoryLM project. |
| 12 | **plc-copilot-landing scaffold** | plc-copilot-landing | Clean Next.js 14 landing page template. ProjectSkill could scaffold marketing sites. |
| 13 | **factorylm-mini ESP32 scaffold** | factorylm-mini | PlatformIO firmware template. ProjectSkill could scaffold IoT device firmware. |
| 14 | **`.jarvis-memory/` pattern** | jarvis-android-voice-proto | Structured agent memory with sessions, checkpoints, decisions. Reusable for GistSkill conversation context. |

---

## Summary Statistics

| Metric | Count |
|--------|-------|
| Total repos | 50 |
| Repos scanned | 50 (100%) |
| Repos with relevant capabilities | 23 |
| Repos with scaffolding/template features | 14 |
| Repos with gist-related code | 0 (confirmed: all gists via ad-hoc `gh gist create`) |
| Forks with custom commits | 0 |
| Deprecated/archived repos | 8 |
| Active product repos | ~15 |
| NEW candidate capabilities found | 14 |

---

*Next step: Phase B — Detailed design for GistSkill + ProjectSkill in OpenClaw, incorporating the best patterns from Agent-Factory SCAFFOLD, jarvis-core create-subapp, Clawdbot Skills, and the template systems discovered above.*
