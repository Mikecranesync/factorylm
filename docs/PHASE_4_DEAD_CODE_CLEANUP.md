# Phase 4: Dead Code & Structural Cleanup Report

**Date:** 2026-02-12  
**Branch:** `chore/phase-4-dead-code-cleanup`  
**Prior Phases:** Phase 1 (PLC Dedup), Phase 2 (Secrets Audit), Phase 3 (Observability)

---

## A. Dead/Unused Scripts (`scripts/`)

### A1. One-Time VPS Fix Scripts (Already Applied)

| # | File | What It Does | Action | Risk |
|---|------|-------------|--------|------|
| 1 | `scripts/fix_config.py` | Patches `/root/.clawdbot/clawdbot.json` — sets Telegram allowlist to user `8445149012` | **DELETE** | SAFE — one-time fix, already applied, and targets the old Clawdbot path (pre-OpenClaw migration) |
| 2 | `scripts/secure_vps.py` | Identical purpose to `fix_config.py` — same exact Telegram lockdown, same file path | **DELETE** | SAFE — literal duplicate of fix_config.py |
| 3 | `scripts/fix_openclaw_vps.py` | Patches `/root/.openclaw/openclaw.json` — fixes gateway bind + disables otel plugin | **DELETE** | SAFE — one-time fix, already applied |
| 4 | `scripts/fix_vps_models.py` | Sets model primary to `claude-sonnet-4`, fallbacks to gemini/opus | **DELETE** | SAFE — one-time fix, already applied per MEMORY.md |
| 5 | `scripts/add_groq.py` | Adds Groq provider to `/root/.clawdbot/clawdbot.json` | **DELETE** | SAFE — targets deprecated Clawdbot path, one-time fix |
| 6 | `scripts/add_groq_vps.py` | Adds Groq provider to `/root/.openclaw/openclaw.json` | **DELETE** | SAFE — one-time fix, already applied |
| 7 | `scripts/update_vps_key.py` | Updates Anthropic API key in OpenClaw auth profiles | **DELETE** | SAFE — one-time credential rotation, contains `[REDACTED]` placeholder anyway |
| 8 | `scripts/verify_groq.py` | Reads `/root/.clawdbot/clawdbot.json` to verify Groq was added | **DELETE** | SAFE — diagnostic for old Clawdbot path, one-time use |
| 9 | `scripts/migrate_to_openclaw.py` | Migrates Clawdbot config/sessions/credentials to OpenClaw dir structure | **DELETE** | SAFE — migration completed, one-time script |

### A2. One-Time Demo Scripts (Demo Date: Feb 10, 2026 — Already Passed)

| # | File | What It Does | Action | Risk |
|---|------|-------------|--------|------|
| 10 | `scripts/deploy_mission_brief.py` | Pushes "MISSION BRIEF" file to laptops via Jarvis Node API for the Catapult Lakeland demo | **DELETE** | SAFE — demo is over (Feb 10), hardcoded Tailscale IPs |
| 11 | `scripts/message_plc_claude.py` | Sends a one-time "YOU ARE CONNECTED" message to the PLC laptop via Jarvis Node | **DELETE** | SAFE — one-time message, hardcoded IPs |
| 12 | `scripts/notify_plc.py` | Writes `NETWORK_STATUS.txt` and `NETWORK_CREDENTIALS.txt` to PLC laptop desktop | **DELETE** | SAFE — one-time notification, hardcoded IPs, contains credentials in plaintext |

### A3. Reusable Scripts (KEEP)

| # | File | What It Does | Action | Risk |
|---|------|-------------|--------|------|
| 13 | `scripts/diagnosis_service.py` | FastAPI service bridging Telegram→PLC→LLM for diagnostics | **KEEP** | — Active service, config uses env vars properly |
| 14 | `scripts/llm_demo.py` | Interactive CLI demo: connect to Micro 820, ask LLM questions about factory state | **KEEP** | LOW — but has stale `mixtral-8x7b-32768` model ref (see F1) |
| 15 | `scripts/test_connection.py` | Modbus TCP connection tester for Micro 820 PLC | **KEEP** | — Useful diagnostic tool |
| 16 | `scripts/factorylm_skill.js` | Clawdbot/OpenClaw skill for routing factory questions | **KEEP** | — Active integration code |
| 17 | `scripts/FACTORYLM_INTEGRATION.md` | Integration doc for how Clawdbot routes to diagnosis service | **KEEP** | — Reference documentation |
| 18 | `scripts/.env.example` | Template for environment variables | **KEEP** | — but has stale model refs (see F2) |
| 19 | `scripts/openclaw.service` | systemd unit file for OpenClaw on VPS | **KEEP** | — Active deployment artifact |

### A4. Ralph Automation Files

| # | File | What It Does | Action | Risk |
|---|------|-------------|--------|------|
| 20 | `scripts/ralph/prd.json` | PRD for Ralph agent's PLC-client build | **ASK_MIKE** — Move to `docs/ralph-archive/` or delete? | SAFE |
| 21 | `scripts/ralph/progress.txt` | Ralph agent's progress log during PLC client build | **ASK_MIKE** — Move to `docs/ralph-archive/` or delete? | SAFE |
| 22 | `scripts/ralph/prompt.md` | Prompt/instructions for the Ralph agent | **ASK_MIKE** — Move to `docs/ralph-archive/` or delete? | SAFE |

> **Summary:** 12 scripts can be safely deleted. 7 should be kept. 3 Ralph files need a decision.

---

## B. Junk Files at Root

| # | File | What It Is | Action | Risk |
|---|------|-----------|--------|------|
| 1 | `nul` | Empty file — Windows artifact from `> nul` redirection creating a literal file | **DELETE** | SAFE — 0 bytes, no content |
| 2 | `Stop-Process` | Empty file — PowerShell artifact from `Stop-Process` being interpreted as a filename | **DELETE** | SAFE — 0 bytes, no content |
| 3 | `openclaw` | Empty file — likely artifact from a typo or incomplete command | **DELETE** | SAFE — 0 bytes, no content |
| 4 | `${CLAUDE_ENV_FILE}` | Contains 5 duplicate lines of `RALPH_PROJECT=C:/Users/hharp/OneDrive/Desktop/Rivet-PRO` — template variable was written as literal filename | **DELETE** | SAFE — local path, not useful |
| 5 | `My-Ralph/nul` | Same Windows `nul` artifact inside My-Ralph subproject | **DELETE** | SAFE — 0 bytes |
| 6 | `Ewon_replacer.md` | 498-line product spec for "RIVET Pi Gateway" — an eWON-replacement IoT gateway. Comprehensive but appears to be a brainstorming/prompt doc, not active code. | **MOVE** to `docs/specs/Ewon_replacer.md` | SAFE — documentation, not referenced by code |
| 7 | `RESUME_PROMPT.md` | Session context from Feb 2-3 for the Catapult demo. Contains Tailscale IPs, WiFi SSID, Balena fleet ID. Demo is over. | **DELETE** or **MOVE** to `docs/archive/` | LOW — contains some useful network reference but demo is past |
| 8 | `MIGRATION.md` | Migration plan for consolidating old repos into this monorepo. Still has many unchecked items (Phase 3-6). | **KEEP** | — Still relevant as a tracking document |
| 9 | `docs/Claude progress.txt` | 700+ line raw dump of a Claude Code CLI session. Contains session logs, Balena setup walkthrough, USB configurator design brief. | **DELETE** | SAFE — raw session transcript, not documentation. The USB configurator design is interesting but should be extracted to a proper spec if needed |

---

## C. Confusing Naming

| # | Item | Issue | Action | Risk |
|---|------|-------|--------|------|
| 1 | `My-Ralph/` (root directory) | PascalCase with hyphen. Every other top-level dir uses lowercase kebab-case (`plc-client`, `plc-client-factoryio`) or lowercase (`core`, `scripts`, `docs`). Also the name "My-Ralph" is unclear to anyone who doesn't know Ralph is an autonomous dev loop agent. | **RENAME** to `my-ralph/` at minimum. Consider `services/ralph/` to match monorepo convention. | MEDIUM — git rename, imports may reference the path |
| 2 | `plc-client/` vs `plc-client-factoryio/` vs `services/plc-modbus/` | Three directories all containing PLC Modbus client code. Naming doesn't clarify which is canonical. Per Phase 1 analysis this was identified but naming is still confusing. | **ASK_MIKE** — Needs a decision on canonical location | MEDIUM |
| 3 | `scripts/diagnosis_service.py` | This isn't a "script" — it's a full FastAPI microservice (210 lines, REST API, Pydantic models). Lives in `scripts/` with one-time fix scripts. | **MOVE** to `services/diagnosis/` | LOW |
| 4 | `scripts/factorylm_skill.js` | JavaScript file among Python scripts. It's an OpenClaw/Clawdbot skill plugin — should live with OpenClaw config, not in `scripts/`. | **MOVE** to `services/assistant/` or appropriate location | LOW |
| 5 | `pics/` | Generic name. Contains hardware photos (Micro 820, Raspberry Pi, screenshots). | **RENAME** to `docs/images/` or `assets/images/` | SAFE |
| 6 | `.playwright-mcp/` | Contains screenshots from Playwright MCP sessions (edge configurator, homepage). Not Playwright test infrastructure — just captured screenshots. | **KEEP** but consider `.gitignore`-ing if these are ephemeral | LOW |
| 7 | `core/` at root | Has both `core/__init__.py` (package marker) AND `core/src/factorylm/` (actual package). The top-level `core/` acts as both a Python package (`core/__init__.py`) and a directory containing subdirectories like `core/models/`, `core/adapters/`, `core/services/`, `core/i18n/` — but these appear to be empty placeholder directories alongside the real code in `core/src/`. | **ASK_MIKE** — clean up the empty placeholder dirs in `core/` or are they planned? | LOW |

---

## D. Empty or Near-Empty Files

### D1. Valid Package Markers (KEEP)
These are necessary `__init__.py` files for Python package structure even though they're mostly empty:
- All `tests/__init__.py` and `tests/unit/__init__.py` and `tests/integration/__init__.py` files
- `core/__init__.py`, `core/models/__init__.py`, `core/adapters/__init__.py`, `core/i18n/__init__.py`, `core/services/__init__.py`
- `services/plc-modbus/backend/__init__.py`, `services/plc-modbus/tools/__init__.py`
- `My-Ralph/api/__init__.py`

**Action:** KEEP all — they're valid Python package markers.

### D2. NOT_IMPLEMENTED Placeholder Directories

| # | Directory | Status | Action | Risk |
|---|-----------|--------|--------|------|
| 1 | `packages/auth/` | `NOT_IMPLEMENTED.md` + `README.md` only | **KEEP** | — Clearly marked, honest about status |
| 2 | `packages/db/` | `NOT_IMPLEMENTED.md` + `README.md` only | **KEEP** | — Same |
| 3 | `packages/ui/` | `NOT_IMPLEMENTED.md` + `README.md` only | **KEEP** | — Same |
| 4 | `services/api/` | `NOT_IMPLEMENTED.md` + `README.md` only | **KEEP** | — Same |
| 5 | `services/assistant/` | `NOT_IMPLEMENTED.md` + `README.md` only | **KEEP** | — Same |

> These are fine — they're clearly labeled as placeholders. Good pattern.

---

## E. Duplicate or Overlapping Logic

### E1. PLC Client Triplication (KNOWN — Phase 1)

The three PLC directories (`plc-client/`, `plc-client-factoryio/`, `services/plc-modbus/`) contain heavily overlapping code:

| Component | `plc-client/` | `plc-client-factoryio/` | `services/plc-modbus/` |
|-----------|---------------|-------------------------|------------------------|
| `ModbusTCPClient` | ✅ `modbus/client.py` | ✅ `modbus_client.py` | ✅ Copied from factoryio |
| `MachineState` | ✅ `models.py` (Unix timestamps) | ✅ `models.py` (datetime + LLM context) | ✅ Copied from factoryio |
| `MockPLC` | ✅ `plc/mock_plc.py` | ✅ `mock_plc.py` (richer) | ✅ Copied from factoryio |
| `BasePLCClient` | ✅ `plc/base.py` | ✅ `base.py` | ✅ Copied from factoryio |
| `ConnectionManager` | ❌ | ✅ | ✅ Copied from factoryio |
| Backend API | ❌ | ❌ | ✅ FastAPI routes + services |

**Key finding:** `plc-client-factoryio/` and `services/plc-modbus/src/factorylm_plc/` are **literal file-for-file copies**. The `plc-client/` version is an earlier, simpler implementation.

**Action:** **ASK_MIKE** — This needs the Phase 1 dedup decision finalized. Recommend: keep `services/plc-modbus/` as canonical (has backend API), delete `plc-client/` (earlier version), keep `plc-client-factoryio/` only if it's the "install on PLC laptop" variant.

**Risk:** MEDIUM — need to verify which is deployed where before deleting.

### E2. `fix_config.py` ≡ `secure_vps.py`

These two scripts are functionally identical — both lock Telegram to allowlist with user `8445149012` on the same Clawdbot config file. Both are already flagged for deletion in Section A.

---

## F. Stale References

### F1. Old Model Names Still in Code

| # | File | Stale Reference | Current Model | Action | Risk |
|---|------|----------------|---------------|--------|------|
| 1 | `scripts/llm_demo.py:189` | `model="mixtral-8x7b-32768"` hardcoded in Groq fallback | `llama-3.3-70b-versatile` | **FIX** — update model name | LOW |
| 2 | `scripts/.env.example:40` | `# GROQ_MODEL=mixtral-8x7b-32768` | `llama-3.3-70b-versatile` | **FIX** — update comment | SAFE |
| 3 | `scripts/.env.example:41` | `# CLAUDE_MODEL=claude-3-haiku-20240307` | `claude-sonnet-4-20250514` | **FIX** — update comment | SAFE |
| 4 | `core/src/factorylm/llm/groq_client.py:32,41` | `DEFAULT_MODEL = "mixtral-8x7b-32768"`, pricing table uses mixtral | `llama-3.3-70b-versatile` | **FIX** | MEDIUM — affects runtime defaults |
| 5 | `core/src/factorylm/llm/claude_client.py:33-34,39` | `DEFAULT_MODEL = "claude-3-sonnet-20240229"`, pricing includes claude-3-haiku | `claude-sonnet-4-20250514` | **FIX** | MEDIUM — affects runtime defaults |
| 6 | `core/README.md:47,82,84` | References mixtral and claude-3-sonnet as defaults | Current models | **FIX** — update docs | SAFE |
| 7 | `core/docs/LLM_INTEGRATION.md` | Multiple references to mixtral, claude-3-sonnet, claude-3-haiku as defaults/options | Current models | **FIX** — update docs | SAFE |
| 8 | `core/docs/SETUP.md:60` | `LLM_MODEL=mixtral-8x7b-32768` in setup instructions | Current model | **FIX** — update docs | SAFE |
| 9 | `core/tests/conftest.py:16,84,116` | Test fixtures use mixtral and claude-3-sonnet model names | N/A | **KEEP** — tests can reference old models, they're mocked anyway | SAFE |
| 10 | `core/tests/` (multiple files) | Unit/integration tests reference old model names | N/A | **KEEP** — these are test expectations, changing them requires updating test logic | LOW |
| 11 | `docs/Architecture.md:316-320` | Documents the stale→current transition — this is correct historical context | N/A | **KEEP** — it's documenting the change itself | SAFE |
| 12 | `scripts/add_groq.py`, `scripts/add_groq_vps.py` | Reference `deepseek-r1-distill-llama-70b` | N/A | **DELETE** — these scripts are being deleted anyway (Section A) | SAFE |

> **Note:** The `core/` stale model defaults (F4, F5) were already identified in `docs/Architecture.md` as needing update. The docs say the defaults were updated to `llama-3.3-70b-versatile` and `claude-sonnet-4-20250514`, but **the actual source code still has the old defaults**. This is a real bug.

### F2. Hardcoded Tailscale IPs

All of these appear in scripts being deleted (Section A) or in session docs being deleted/archived (Section B):

- `100.68.120.99` (VPS/Jarvis) — in `RESUME_PROMPT.md`, `MEMORY.md`, `deploy_mission_brief.py`, etc.
- `100.72.2.99` (PLC Laptop) — in `diagnosis_service.py` (uses env var with fallback), `deploy_mission_brief.py`, etc.
- `100.83.251.23` (Travel Laptop) — same files
- `100.102.30.102` — in `notify_plc.py`, `message_plc_claude.py`

**Action:** Most go away with script deletions. `diagnosis_service.py` correctly uses `os.getenv()` with the IPs as fallback defaults — acceptable.

### F3. Clawdbot References (Deprecated Name)

Multiple scripts reference `/root/.clawdbot/` paths. All of these scripts are already flagged for deletion in Section A:
- `add_groq.py`, `fix_config.py`, `secure_vps.py`, `verify_groq.py`, `migrate_to_openclaw.py`

The `factorylm_skill.js` comment says "for Clawdbot" — minor, could update to "OpenClaw" but not critical.

---

## Summary Action Items

### Immediate Deletions (SAFE — 0 risk of breaking anything)

```
# Root junk files
nul
Stop-Process
openclaw
${CLAUDE_ENV_FILE}
My-Ralph/nul

# One-time VPS fix scripts
scripts/fix_config.py
scripts/secure_vps.py
scripts/fix_openclaw_vps.py
scripts/fix_vps_models.py
scripts/add_groq.py
scripts/add_groq_vps.py
scripts/update_vps_key.py
scripts/verify_groq.py
scripts/migrate_to_openclaw.py

# One-time demo scripts (demo is over)
scripts/deploy_mission_brief.py
scripts/message_plc_claude.py
scripts/notify_plc.py

# Session logs that shouldn't be in git
docs/Claude progress.txt
```

**Total: 17 files to delete**

### Moves/Renames (LOW risk)

```
RESUME_PROMPT.md → docs/archive/RESUME_PROMPT_2026-02-03.md (or delete)
Ewon_replacer.md → docs/specs/Ewon_replacer.md
pics/ → docs/images/
scripts/diagnosis_service.py → services/diagnosis/main.py
scripts/factorylm_skill.js → services/assistant/factorylm_skill.js
```

### Code Fixes (MEDIUM risk — affects runtime)

1. Update `core/src/factorylm/llm/groq_client.py` DEFAULT_MODEL: `mixtral-8x7b-32768` → `llama-3.3-70b-versatile`
2. Update `core/src/factorylm/llm/claude_client.py` DEFAULT_MODEL: `claude-3-sonnet-20240229` → `claude-sonnet-4-20250514`
3. Update `scripts/llm_demo.py` hardcoded model: `mixtral-8x7b-32768` → `llama-3.3-70b-versatile`
4. Update `scripts/.env.example` commented model names
5. Update `core/README.md`, `core/docs/LLM_INTEGRATION.md`, `core/docs/SETUP.md` model references

### Decisions Needed from Mike

1. **PLC directories:** Which is canonical? `plc-client/`, `plc-client-factoryio/`, or `services/plc-modbus/`?
2. **`scripts/ralph/`:** Archive to `docs/ralph-archive/` or delete?
3. **`My-Ralph/` rename:** Rename to `my-ralph/` or move to `services/ralph/`?
4. **Empty dirs in `core/`:** Delete `core/models/`, `core/adapters/`, `core/i18n/`, `core/services/` (empty placeholders alongside real code in `core/src/`)?

---

*Report generated by Phase 4 cleanup scan. All files were read and analyzed individually.*
