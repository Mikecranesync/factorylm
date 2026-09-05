# AGENTS.md — Instructions for AI Agents Working in This Repo

**Product direction updated:** 2026-09-05; technical maturity details below require current verification.

---

## Step 1: Read the Vision

Before doing ANY work, read **[README.md](README.md)**, the shared **[NORTH_STAR.md](NORTH_STAR.md)**, and the **[delivery plan](docs/product/2026-09-05-sellable-app-alignment.md)**. Improve the existing mobile app in `Mikecranesync/MIRA`; this repo supplies reusable supporting capabilities. Link tasks to [MIRA #3586](https://github.com/Mikecranesync/MIRA/issues/3586) and [factorylm #227](https://github.com/Mikecranesync/factorylm/issues/227). The approved direction supersedes older channel/roadmap priorities, while existing safety and engineering rules remain in force.

Key takeaways:
- The existing mobile app is the customer front door; MIRA is the assistant
- Slack/Foreman is the internal delivery command center
- Tie work to app usefulness, release proof, customer learning, or an existing maintenance obligation
- 4-layer intelligence stack (Layer 0 = code/KB → Layer 3 = cloud AI)
- Intelligence flows DOWNWARD — the goal is LESS AI over time
- **Read-only** — FactoryLM never writes to PLCs
- Mike approves what ships

---

## Step 2: Understand What's Real

Not everything in this repo is production code. Check the maturity map:

| Component | Status | Test Command |
|-----------|--------|-------------|
| `core/` — LLM abstraction | ✅ Production (148 tests) | `cd core && pytest` |
| `my-ralph/` — Dev loop agent | ✅ Production (321 tests) | `cd my-ralph && npm test` |
| `services/plc-modbus/` — PLC client + API | ✅ Working (162 tests) | `cd services/plc-modbus && pytest` |
| `services/plc-copilot/` — Telegram bot | ✅ Working (no tests) | Manual |
| `services/diagnosis/` — PLC→LLM bridge | ✅ Working (no tests) | `uvicorn main:app --port 8200` |
| `apps/cmms/` — CMMS web app | ⚠️ Forked, not rebranded | — |
| `docs/archive/plc-client-v1/` | 📦 Archived | Tests migrated to plc-modbus |
| `apps/dashboard/`, `apps/web/`, `services/api/`, `services/assistant/`, `packages/auth/`, `packages/db/`, `packages/ui/` | 🔴 Placeholder | Not implemented |

If a directory has `NOT_IMPLEMENTED.md` or `DEPRECATED.md`, don't try to build on it.

---

## Step 3: Follow the Rules

### Git Workflow

1. **Never commit to `main`.** Create a branch: `feat/`, `fix/`, `chore/`, `docs/`
2. **Run `git status` before changing anything.** Summarize what's dirty.
3. **After changes, show:**
   - Plain English explanation
   - Key parts of the diff
   - Suggested commit message (`type: description`)
   - Suggested PR title + description
4. **Never force-push.** If history is messy, ask Mike.
5. **Never push without Mike's approval.**

### Testing

- **Python:** `pytest` (standard across all Python packages)
- **Bash (My-Ralph):** `npm test` / `bats`
- Run tests before proposing any commit: `cd core && pytest`, `cd services/plc-modbus && pytest`
- If you change code that has tests, the tests must still pass.
- If you add code with no tests, propose 2–5 small tests.

### Secrets

- **Never hardcode API keys, tokens, or passwords.** Use `os.getenv()` / `process.env`.
- **Never print secret values** in logs or output.
- All secrets are managed via **Doppler**. See `docs/Config.md` for env var names.
- If you need a secret value, ask Mike — don't guess or use placeholders that look real.

### Documentation

When you change something, update:
- `docs/Architecture.md` if you change repo structure
- `docs/Config.md` if you add/change env vars
- `docs/Observability.md` if you change tracing/logging
- `MEMORY.md` with a session log entry

---

## Step 4: Know the Key Files

| File | Purpose | When to Read |
|------|---------|-------------|
| `README.md` | THE VISION — 4-layer stack, routing, philosophy | Always, first |
| `CLAUDE.md` | Quick reference for Claude agents | Auto-loaded |
| `AGENTS.md` | This file — rules for all AI agents | Always |
| `docs/Architecture.md` | Directory map, maturity table, entrypoints, refactor log | When exploring the repo |
| `docs/Config.md` | Env vars, Doppler layout, per-service config | When touching config |
| `docs/Observability.md` | Axiom (logs) + Honeycomb (traces) setup | When touching observability |
| `docs/OPENCLAW_INSTANCES.md` | OpenClaw bot instance map (3 bots, configs, providers) | When touching OpenClaw |
| `docs/SECRETS_AUDIT.md` | Known secrets, rotation status, remediation | When touching secrets |
| `MEMORY.md` | Session history, integration map, resume instructions | When resuming work |
| `MIGRATION.md` | Monorepo migration tracking | When consolidating repos |

---

## Step 5: Know the Stack

### Languages & Frameworks

| Where | Language | Framework | Package Manager |
|-------|----------|-----------|----------------|
| `core/` | Python 3.11+ | — | pip / setuptools |
| `services/plc-modbus/` | Python 3.9+ | FastAPI | pip / setuptools |
| `services/plc-copilot/` | Python 3.9+ | python-telegram-bot | pip |
| `my-ralph/` | Bash + Python | BATS (tests), FastAPI (API) | npm (tests), pip (API) |
| `apps/cmms/api/` | Java 17 | Spring Boot | Maven |
| `apps/cmms/frontend/` | TypeScript | React 18 + MUI | npm |
| Root monorepo | — | Turborepo | npm workspaces |

### External Services

| Service | Env Var | Used By |
|---------|---------|---------|
| Groq (LLM) | `GROQ_API_KEY` | core, OpenClaw |
| Anthropic (LLM) | `CLAUDE_API_KEY` | core, OpenClaw |
| Google Gemini (Vision) | `GEMINI_API_KEY` | plc-copilot |
| Telegram | `TELEGRAM_BOT_TOKEN` | plc-copilot |
| Atlas CMMS | `CMMS_API_URL` | plc-copilot |
| Honeycomb (traces) | `HONEYCOMB_API_KEY` | all services |
| Axiom (logs) | `AXIOM_TOKEN` | VPS log shippers |
| Doppler (secrets) | CLI auth | all services |

### Observability

Two systems, both optional:
- **Axiom** — log aggregation via Vector shippers (VPS only)
- **Honeycomb** — distributed tracing via OTel SDK (all services)
- Python services use `from factorylm.observability import init_tracing`
- Node.js services use `scripts/honeycomb/tracing.js` via `NODE_OPTIONS`

---

## Step 6: Common Tasks

### "Add a new LLM provider"
1. Create `core/src/factorylm/llm/new_provider_client.py`
2. Follow the pattern in `groq_client.py` — same interface
3. Add default model to `core/src/factorylm/config.py`
4. Add tests in `core/tests/unit/test_new_provider_client.py`
5. Update `docs/Config.md` with new env var
6. Update `docs/Architecture.md` external services table

### "Add a new service"
1. Create `services/new-service/` with `pyproject.toml`
2. Add `from factorylm.observability import init_tracing` at startup
3. Add `[tool.pytest.ini_options]` to pyproject.toml
4. Create `services/new-service/tests/`
5. Update `docs/Architecture.md` maturity table
6. Update `docs/Config.md` with required env vars

### "Debug a failing OpenClaw bot"
1. Read `docs/OPENCLAW_INSTANCES.md` for instance details
2. Check which providers are working (Groq is most reliable)
3. SSH commands: `ssh vps "systemctl status openclaw"`
4. Logs: `ssh vps "tail -f /tmp/openclaw/openclaw-$(date +%Y-%m-%d).log"`
5. Config: `ssh vps "cat /root/.openclaw/openclaw.json"`

---

## Don'ts

- **Don't** propose microservice architectures for things that should be functions
- **Don't** add abstractions "for future use" — build what's needed now
- **Don't** change README.md unless Mike says "update the README" (it's the vision)
- **Don't** touch `docs/archive/plc-client-v1/` — it's archived (canonical code is in `services/plc-modbus/`)
- **Don't** assume placeholder directories have code — check for `NOT_IMPLEMENTED.md`
- **Don't** use outdated model names (mixtral, claude-3-sonnet) — check `config.py` for current defaults
- **Don't** use LangSmith/Phoenix/CodeSee — these are mentioned in old docs but not currently used
