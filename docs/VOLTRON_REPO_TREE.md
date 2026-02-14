# Voltron — Proposed Repo Structure

**Date:** 2026-02-12  
**Status:** Proposal — not yet created

---

## Option A: New repo (`voltron/`)

Clean break. Recommended.

```
voltron/
│
├── README.md                      # Vision + quick start
├── ARCHITECTURE.md                # → copy of VOLTRON_ARCHITECTURE.md
├── AGENTS.md                      # AI agent instructions
├── pyproject.toml                 # Root Python project (src layout)
├── docker-compose.yaml            # Dev stack (Postgres, Matrix, sample node)
│
├── config/                        # All configuration (never hardwired)
│   ├── models.yaml                # LLM providers, tiers, fallback chains
│   ├── nodes/                     # Per-node config templates
│   │   ├── plc-micro820.yaml      # PLC reader node config
│   │   ├── vps-worker.yaml        # VPS software node config
│   │   └── dev-local.yaml         # Local dev node config
│   └── matrix.yaml                # Matrix settings (DB, Telegram token, ports)
│
├── matrix/                        # Central controller (runs on VPS)
│   ├── __init__.py
│   ├── main.py                    # Entrypoint — starts bot + node registry
│   ├── bot/                       # Telegram bot layer
│   │   ├── __init__.py
│   │   ├── handler.py             # Message handler (routes to intent classifier)
│   │   ├── commands.py            # /status, /plc, /ask, /nodes, /cost, /brain
│   │   └── formatter.py           # Response formatting (markdown, tables, emoji)
│   ├── router/                    # Intelligence routing
│   │   ├── __init__.py
│   │   ├── intent.py              # Classify operator intent → node + tier
│   │   └── dispatch.py            # Send task to node, collect result
│   ├── llm/                       # LLM client (model-agnostic)
│   │   ├── __init__.py
│   │   ├── client.py              # Unified interface — send prompt, get response
│   │   ├── providers/             # One file per provider
│   │   │   ├── __init__.py
│   │   │   ├── anthropic.py       # Claude (Opus, Sonnet, Haiku)
│   │   │   ├── groq.py            # Groq (Llama 3.3)
│   │   │   ├── google.py          # Gemini
│   │   │   └── local.py           # Ollama / local models
│   │   └── tier.py                # Tier selection logic (big vs small brain)
│   ├── registry/                  # Node management
│   │   ├── __init__.py
│   │   ├── node_registry.py       # Register, deregister, health tracking
│   │   └── heartbeat.py           # Monitor node liveness
│   ├── memory/                    # Conversation + task persistence
│   │   ├── __init__.py
│   │   ├── conversation.py        # Chat history (Postgres)
│   │   ├── task_log.py            # Task dispatch/result log
│   │   └── cost_tracker.py        # LLM spend tracking
│   └── db/                        # Database layer
│       ├── __init__.py
│       ├── postgres.py            # Postgres connection + migrations
│       └── migrations/            # SQL migration files
│           └── 001_initial.sql
│
├── node/                          # Generic node daemon (runs anywhere)
│   ├── __init__.py
│   ├── daemon.py                  # Node daemon entrypoint — connects to Matrix
│   ├── policy.py                  # Policy engine — reads policy.yaml, enforces rules
│   ├── soul.py                    # Soul loader — reads soul.md, provides to LLM context
│   ├── executor.py                # Tool executor — runs allowed tools, blocks denied
│   ├── heartbeat.py               # Periodic check-in with Matrix
│   ├── local_db.py                # SQLite for local cache/logs
│   └── tools/                     # Built-in tools (nodes pick which to enable)
│       ├── __init__.py
│       ├── plc_reader.py          # Read PLC via Modbus TCP (from factorylm_plc)
│       ├── knowledge_search.py    # Search vector DB / knowledge base
│       ├── diagnostic.py          # Run diagnostic routines
│       └── web_search.py          # Web search (for software nodes)
│
├── shared/                        # Code shared between matrix and node
│   ├── __init__.py
│   ├── protocol.py                # Matrix↔Node message protocol (dataclasses)
│   ├── config_loader.py           # YAML config loader
│   └── observability.py           # OTel tracing setup (Honeycomb)
│
├── templates/                     # Template files for new nodes
│   ├── soul.md                    # Soul file template
│   └── policy.yaml                # Policy file template
│
├── scripts/                       # Dev and deployment helpers
│   ├── dev.sh                     # Start Matrix + sample node locally
│   ├── deploy-matrix.sh           # Deploy Matrix to VPS
│   ├── deploy-node.sh             # Deploy node to any host
│   ├── create-node.py             # Interactive: create a new node (soul + policy + config)
│   └── migrate-db.py              # Run Postgres migrations
│
├── tests/                         # All tests
│   ├── conftest.py
│   ├── unit/
│   │   ├── test_policy_engine.py
│   │   ├── test_tier_selection.py
│   │   ├── test_llm_client.py
│   │   ├── test_node_registry.py
│   │   └── test_intent_classifier.py
│   ├── integration/
│   │   ├── test_matrix_node_flow.py
│   │   └── test_telegram_commands.py
│   └── fixtures/
│       ├── sample_soul.md
│       ├── sample_policy.yaml
│       └── sample_models.yaml
│
└── docs/
    ├── SETUP.md                   # How to get running from zero
    ├── ADDING_A_NODE.md           # How to create and register a new node
    ├── ADDING_A_PROVIDER.md       # How to add a new LLM provider
    └── SECURITY.md                # Soul/policy guarantees, threat model
```

---

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Single Python repo** | No Turborepo, no npm, no Java. Python everywhere. |
| **`config/` separate from code** | Swap models, add nodes, change policies without touching code |
| **`matrix/llm/providers/`** one file per provider | Add a provider = add one file + config entry. No interface changes. |
| **`node/tools/`** modular tools | Each node enables tools via `policy.yaml`. Adding a tool = one file. |
| **`shared/protocol.py`** | Matrix↔Node protocol defined once. Both sides import it. |
| **`templates/`** | `create-node.py` copies these to bootstrap a new node. |
| **No placeholder directories** | If it doesn't exist yet, it doesn't get a directory. |

---

## What Gets Migrated From FactoryLM

See `VOLTRON_MIGRATION.md` for the full plan.

| FactoryLM Source | Voltron Destination | What Changes |
|---|---|---|
| `core/src/factorylm/llm/` | `matrix/llm/providers/` | Refactored to unified interface |
| `core/src/factorylm/config.py` | `shared/config_loader.py` | YAML-based instead of env-only |
| `core/src/factorylm/observability.py` | `shared/observability.py` | Direct port |
| `services/plc-modbus/src/factorylm_plc/` | `node/tools/plc_reader.py` | Slim wrapper around modbus_client |
| `services/plc-copilot/photo_to_cmms_bot.py` | `matrix/bot/` | Telegram patterns reused |
| OpenClaw `SOUL.md` concept | `templates/soul.md` + `node/soul.py` | Formalized with loader |
