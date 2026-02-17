# TRC-2026-02-16-005: Wire Jarvis to KB + Maintenance LLM

| Field | Value |
|-------|-------|
| **ID** | TRC-2026-02-16-005 |
| **Date** | 2026-02-16 |
| **Author** | Claude Code (Travel Laptop) |
| **Duration** | ~30m |
| **Type** | feature-build |
| **Services** | openclaw |
| **Devices** | vps, travel-laptop |
| **Trigger** | Jarvis bouncing messages off Groq without using KB or maintenance LLM |

---

## Context

Jarvis was online with personality and skills working, but DiagnoseSkill and ChatSkill only routed to Groq LLM. The VPS has 4,617 knowledge atoms in PostgreSQL/pgvector (rivet DB) and a maintenance LLM on the PLC laptop (Ollama at 100.72.2.99:11434) — neither was being used.

## What Happened

1. Tagged current stable as `v0.9.0-jarvis-baseline` (already existed)
2. Created `feat/kb-maint-llm` branch from `fix/jarvis-personality`
3. Installed `asyncpg` in OpenClaw venv
4. Created `KnowledgeConnector` — async PostgreSQL connector using full-text search (GIN index)
5. Added config flags: `kb_enabled`, `kb_postgres_url`, `maint_llm_enabled`, `maint_llm_url`
6. Wired KB connector into `app.py` (conditional on `kb_enabled`)
7. Updated `DiagnoseSkill` to query KB for fault codes and descriptions before LLM call
8. Updated `ChatSkill` to search KB for relevant procedures/concepts before LLM call
9. Created `MaintenanceLLMConnector` for Ollama on PLC laptop
10. Pushed branch, opened PR #2 on openclaw repo

## Changes Made

| File/Config | Before | After | Why |
|-------------|--------|-------|-----|
| `openclaw/connectors/knowledge.py` | (new) | KB connector with search, fault code lookup, symptom search | Access 4,617 knowledge atoms |
| `openclaw/connectors/maintenance_llm.py` | (new) | Ollama connector with generate, list_models | Layer 1/2 inference on PLC laptop |
| `openclaw/config.py` | No KB/maint config | `kb_enabled`, `kb_postgres_url`, `maint_llm_enabled`, `maint_llm_url` | Feature flags, OFF by default |
| `openclaw/app.py` | 4 connectors | 6 connectors (KB + maint LLM conditional) | Wire new connectors |
| `openclaw/skills/builtin/diagnose.py` | Tags + faults -> Groq | Tags + faults + KB search -> Groq (enriched prompt) | Known solutions inform LLM |
| `openclaw/skills/builtin/chat.py` | User text -> Groq | User text + KB search -> Groq (enriched prompt) | Procedures/concepts inform LLM |

## Outcome

- Branch `feat/kb-maint-llm` pushed with 5 commits
- PR #2 opened: https://github.com/Mikecranesync/openclaw/pull/2
- **NOT deployed** — Mike reviews and deploys manually
- All features behind flags, OFF by default — zero behavior change until enabled

## Queryable Tags

- **config-keys**: kb_enabled, kb_postgres_url, maint_llm_enabled, maint_llm_url
- **ports**: 5432 (PostgreSQL), 11434 (Ollama)
- **dependencies**: asyncpg
- **tables**: knowledge_atoms (4,617 rows)

## Related

- **PR**: https://github.com/Mikecranesync/openclaw/pull/2
- **Baseline tag**: `v0.9.0-jarvis-baseline`
- **Commits**: `8e5dc2d`, `8556e7c`, `850d388`, `3dbc463`, `1ebe8e9`
- **Prior Traces**: [TRC-2026-02-16-004](./2026-02-16_tts-emoji-ack.md)
