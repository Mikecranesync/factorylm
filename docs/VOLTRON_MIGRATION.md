# Voltron Migration Plan — Mining FactoryLM

**Date:** 2026-02-12  
**Status:** Plan only — no code moved yet

---

## Strategy

**Selective migration, not fork.** We create Voltron from scratch and pull in only the tested, working pieces from FactoryLM. No dead code, no placeholders, no deprecated patterns come along.

### Three Rules

1. **If it has tests and they pass → candidate for migration.**
2. **If it's a pattern/approach (not code) → document and reimplement cleanly.**
3. **If it's aspirational/placeholder → leave it behind.**

---

## Phase 0: Scaffold (Before Any Migration)

Create the `voltron/` repo with the structure from `VOLTRON_REPO_TREE.md`:

- [ ] Init repo with `pyproject.toml`, `.gitignore`, `README.md`
- [ ] Create directory skeleton (`matrix/`, `node/`, `shared/`, `config/`, `tests/`)
- [ ] Set up pytest, basic CI (GitHub Actions)
- [ ] Create `ARCHITECTURE.md` (from `VOLTRON_ARCHITECTURE.md`)
- [ ] Create template soul.md and policy.yaml
- [ ] Set up Postgres dev environment (docker-compose)

**No FactoryLM code in this phase.** Just scaffolding.

---

## Phase 1: LLM Client (from `core/`)

### What to mine

| Source File | Tests? | Migrate? | Notes |
|---|---|---|---|
| `core/src/factorylm/llm/groq_client.py` | ✅ Yes | ✅ | Rewrite to unified interface |
| `core/src/factorylm/llm/claude_client.py` | ✅ Yes | ✅ | Rewrite to unified interface |
| `core/src/factorylm/llm/deepseek_client.py` | ✅ Yes | ✅ | Rewrite to unified interface |
| `core/src/factorylm/llm/flm_client.py` | ✅ Yes | ⚠️ | Future — skip for v0.1 |
| `core/src/factorylm/config.py` | ✅ Yes | 🔄 | Pattern only — Voltron uses YAML config |
| `core/src/factorylm/observability.py` | ✅ Yes | ✅ | Direct port to `shared/observability.py` |

### What to leave behind

- `core/adapters/`, `core/models/`, `core/services/`, `core/i18n/` — empty stubs
- Env-var-only config pattern — Voltron uses YAML + env vars for secrets only
- Old model defaults (mixtral, claude-3-sonnet) — already fixed but don't carry the baggage

### How to migrate

1. Read each provider client, extract the interface pattern (init, send_message, stream)
2. Create `matrix/llm/client.py` with a unified `LLMClient` class
3. Create one file per provider in `matrix/llm/providers/` following the new interface
4. Port observability.py directly to `shared/observability.py`
5. Write tests that match the existing 148-test coverage

---

## Phase 2: PLC Tools (from `services/plc-modbus/`)

### What to mine

| Source File | Tests? | Migrate? | Notes |
|---|---|---|---|
| `factorylm_plc/modbus_client.py` | ✅ Yes | ✅ | Core Modbus TCP reader |
| `factorylm_plc/micro820.py` | ✅ Yes | ✅ | Allen-Bradley specific config |
| `factorylm_plc/base.py` | ✅ Yes | ✅ | Base PLC class |
| `factorylm_plc/models.py` | ✅ Yes | ✅ | Data models |
| `factorylm_plc/connection_manager.py` | ✅ Yes | ✅ | Connection pooling |
| `factorylm_plc/mock_plc.py` | ✅ Yes | ✅ | Test mock |
| `factorylm_plc/llm4plc.py` | ✅ Yes | 🔄 | Pattern only — Voltron does this differently |
| `factorylm_plc/factory_io.py` | ⚠️ Partial | ⚠️ | Phase 2 — FactoryIO sim support |
| `factorylm_plc/factory.py` | ⚠️ Partial | ⚠️ | Phase 2 |
| `backend/` (FastAPI) | ✅ Yes | ❌ | Not needed — Matrix has its own API |
| `tools/plc_monitor.py` | ✅ Working | 🔄 | Pattern for CLI tool, reimplement |
| `tools/plc_logger.py` | ✅ Working | 🔄 | Pattern for CLI tool, reimplement |
| `factorylm-edge/` | ⚠️ Pi-specific | ⏸️ | Phase 2 — Pi hardware node |

### What to leave behind

- `plc-client/` (V1) — deprecated, old pymodbus API
- `plc-client-factoryio/` (V2) — deprecated duplicate
- FastAPI backend — Voltron nodes don't run their own HTTP servers

### How to migrate

1. Copy `modbus_client.py`, `micro820.py`, `base.py`, `models.py`, `connection_manager.py`, `mock_plc.py` into a working directory
2. Refactor into `node/tools/plc_reader.py` — a single tool that the node's executor can call
3. The tool exposes functions: `read_coils()`, `read_holding_registers()`, `get_plc_status()`
4. Policy engine controls which PLC addresses and functions are allowed
5. Port relevant tests

---

## Phase 3: Telegram Bot (from `services/plc-copilot/` + clawdbot patterns)

### What to mine

| Source | Migrate? | Notes |
|---|---|---|
| `plc-copilot/photo_to_cmms_bot.py` | 🔄 Pattern | Telegram bot setup, handler pattern |
| clawdbot's SOUL.md concept | ✅ | Formalize as `node/soul.py` loader |
| clawdbot's model fallback chain | 🔄 Pattern | Reimplement in `matrix/llm/tier.py` |
| clawdbot's compaction settings | 🔄 Pattern | Implement as Matrix conversation management |

### What to leave behind

- OpenClaw/clawdbot codebase (stays separate, not forked)
- Photo→CMMS specific logic (not relevant to Voltron v0.1)
- Gemini Vision integration (Phase 2 — when camera nodes exist)

### How to migrate

1. Study `photo_to_cmms_bot.py` for Telegram bot setup pattern
2. Build `matrix/bot/` from scratch using `python-telegram-bot` or `aiogram`
3. Implement the 6 v0.1 commands: `/status`, `/plc`, `/ask`, `/nodes`, `/cost`, `/brain`
4. Port the SOUL.md concept into a formal loader with schema validation
5. Port the model fallback chain into `matrix/llm/tier.py`

---

## Phase 4: Observability (from existing setup)

### What to mine

| Source | Migrate? |
|---|---|
| `core/src/factorylm/observability.py` | ✅ Direct port |
| `scripts/honeycomb/tracing.js` | 🔄 Rewrite in Python |
| Axiom Vector config patterns | 🔄 Pattern for node log shipping |

### How to migrate

1. Port `observability.py` to `shared/observability.py`
2. Matrix and every node call `init_tracing()` at startup
3. Honeycomb datasets: `voltron-matrix`, `voltron-node-{id}`
4. Node logs shipped to Axiom (or just Honeycomb traces — simplify)

---

## What We Explicitly Do NOT Migrate

| Component | Why |
|---|---|
| `apps/cmms/` | Forked Java app. Not our code. Not needed. |
| `apps/portal/` | VPS-specific Jarvis brain viewer. Voltron has its own dashboard later. |
| `apps/dashboard/`, `apps/web/` | Placeholders. Nothing to migrate. |
| `services/api/`, `services/assistant/` | Placeholders. Nothing to migrate. |
| `packages/auth/`, `packages/db/`, `packages/ui/` | Placeholders. Nothing to migrate. |
| `my-ralph/` | Separate tool. Stays in its own repo. |
| Turborepo / npm workspace | Voltron is pure Python. No JS build system. |
| `plc-client/` (V1), `plc-client-factoryio/` (V2) | Deprecated. V3 in `services/plc-modbus/` is canonical. |
| LangSmith / Phoenix / CodeSee | Mentioned in old docs, never actually used. |

---

## Migration Checklist (Summary)

- [ ] **Phase 0:** Scaffold Voltron repo (no FactoryLM code)
- [ ] **Phase 1:** Migrate LLM clients → `matrix/llm/providers/`
- [ ] **Phase 1:** Port observability → `shared/observability.py`
- [ ] **Phase 2:** Migrate PLC Modbus library → `node/tools/plc_reader.py`
- [ ] **Phase 3:** Build Telegram bot (new code, patterns from plc-copilot + clawdbot)
- [ ] **Phase 3:** Formalize soul.md + policy.yaml system
- [ ] **Phase 4:** Set up Honeycomb tracing for Matrix + Nodes
- [ ] **Phase 5:** Day-1 deployment (Matrix on DO VPS, 3 nodes)
- [ ] **Phase 6:** Integration test — operator sends Telegram message, gets PLC data back

---

## Success Criteria

When all of this is done, the following should work:

```
Mike sends "/plc" to Voltron Telegram bot
  → Matrix receives message
  → Matrix routes to plc-micro820 node
  → Node reads Modbus coils from 192.168.1.100
  → Node returns PLC state to Matrix
  → Matrix formats response
  → Mike sees PLC state in Telegram
```

Total latency target: < 3 seconds.  
LLM cost for this query: $0.00 (no LLM needed for a direct read).
