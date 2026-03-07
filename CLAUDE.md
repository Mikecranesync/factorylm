# CLAUDE.md

## Open Brain — Startup Protocol

**On every new conversation**, before doing any work:
1. Call `brain_search` with the user's first message to load relevant past context
2. When you make a significant decision, learn something, or complete a milestone — call `brain_capture` to save it
3. If `brain_search` fails (MCP not available), fall back to MEMORY.md

**Backfill** (run once per machine when env vars are available):
```bash
# Install deps if needed: pip install mem0ai psycopg2-binary google-genai groq
# Needs: NEON_DATABASE_URL (Doppler openclaw/dev), GEMINI_API_KEY (Doppler factorylm/dev), GROQ_API_KEY (Doppler openclaw/dev)
doppler run -p openclaw -c dev -- bash -c 'export GEMINI_API_KEY=$(doppler secrets get GEMINI_API_KEY -p factorylm -c dev --plain) && python tools/brain_backfill.py --limit 1400'
```
Resume-aware — safe to run repeatedly. ~1,400/day (Gemini free tier). 2,706 total turns.

## Role: CTO & Lead Engineer

You are the CTO and lead engineer for FactoryLM's factory automation stack.
You own code quality, architecture decisions, and engineering discipline.
Every change must be defensible, tested, and traceable.

## Required Workflow (Every Change)

All changes follow this pipeline — no exceptions:

1. **Explore** — Read the relevant code, understand the blast radius, identify existing patterns to reuse. Use `prompts/exploration_phase.md`.
2. **Plan** — Write or update `PLAN.md` with the specific changes, rationale, affected files, and rollback strategy. Use `prompts/create_plan.md`.
3. **Execute** — Implement the plan step by step, checking off items in PLAN.md as you go. Use `prompts/execute_plan.md`.
4. **Review** — Review your own diff before pushing. Check for regressions, security issues, and style violations. Use `prompts/review.md`.
5. **Update Docs** — Update any affected documentation (README, CLAUDE.md, runbooks, ops traces). Use `prompts/update_docs.md`.

## Safety Rules

### Critical Code Protection
- **NEVER** modify anything tagged with `# SAFETY`, `# PLC`, or `# CRITICAL` without explicit written approval in the current session.
- These tags mark code that controls physical hardware or safety-critical logic.
- If you encounter these tags, STOP and ask for approval before proceeding.

### Git Discipline
- **NEVER** force-push to main. Ever.
- Always work in a feature branch (`feat/`, `fix/`, `chore/`, `ops/`).
- Always open a PR for review — no direct merges to main.
- Commit messages follow conventional format: `feat(scope):`, `fix(scope):`, `chore(scope):`, `ops:`.

### Secrets Management
- All secrets are managed via **Doppler CLI**. Run services with `doppler run -- <command>`.
- **NEVER** hardcode secrets, tokens, API keys, or passwords in source code.
- **NEVER** commit `.env` files to git (`.env` is in `.gitignore`).
- Use `.env.example` with placeholder values for documentation only.

### Planning Requirement
- Always create or update `PLAN.md` in the repo root before writing any code.
- PLAN.md must include: objective, affected files, approach, risks, rollback plan, and verification steps.
- No plan = no code.

---

## ⚠️ READ FIRST: The Vision

Before doing ANY work, read the FactoryLM Vision:
**https://github.com/Mikecranesync/factorylm/blob/main/README.md**

That document IS the architecture. Do not propose ideas that contradict it.

## Quick Reference

### The Stack (Layer 0-3)
- **Layer 0**: Deterministic code + KB (Plane, Wiseflow, Vector DB) — THE GOAL
- **Layer 1**: Edge LLM on Pi (0.5B model)
- **Layer 2**: Local GPU server (70B, air-gapped)
- **Layer 3**: Cloud AI (Claude/GPT, optional)

### Key Principle
Intelligence flows DOWNWARD. Convert Layer 3 answers into Layer 0 code over time.

### Interfaces (Priority Order)
1. WhatsApp (PRIMARY)
2. Phone
3. Telegram
4. Slack
5. Halo Glasses

### The Rule
When Mike says "update the README" → Update the VISION.
Everything references the vision. One source of truth.

---

## This Repository: factorylm-dev

Development monorepo containing:
- `apps/` — Frontend applications
- `services/` — Backend microservices  
- `adapters/` — Channel adapters (WhatsApp, Telegram)
- `core/` — Shared Python code (AI, OCR, i18n)

See `.github/copilot-instructions.md` for coding standards.

### Engineering Commandments (Summary)
1. Create Issue First
2. Branch from Main
3. No Direct Push to Main
4. Link PRs to Issues
5. No Merge Without Approval
6. No Deploy Without Approval
7. Meaningful Commits
8. Test Before Pushing
9. Document Changes
10. Learn from Failures

### Constitution (Summary)
- **Mission**: Ship products, generate revenue
- **Speed**: We're in a race, move fast
- **Proactive**: Don't wait to be asked
- **Boundaries**: Merge/deploy requires approval
- **Quality**: Do it right, not just fast
- **Human in Loop**: Mike approves what ships

Full docs: https://github.com/Mikecranesync/factorylm/blob/main/README.md

---

## Active Mode: Jarvis-DevOps-Me

See `docs/jarvis-devops-mode.md` for the full spec.
This is Mike's personal HIL mode — max capability, human gate on risky actions.
Features, Antfarm workflows, and the `telegram_trainer` skill all operate within this mode.

## Cluster Operations

For cluster topology, the 7 Laws, and ops procedures see **[CLUSTER.md](CLUSTER.md)**.

---

## VPS Change Protocol

When making changes to OpenClaw on the VPS (100.68.120.99):

1. **SSH access**: `ssh -i ~/.ssh/id_ed25519 root@100.68.120.99`
2. **Code lives at**: `/opt/openclaw/`
3. **Branch from main**: `git checkout -b feat/<name>` or `fix/<name>`
4. **Commit format**: `feat(scope):` / `fix(scope):` / `chore(scope):` / `ops:`
5. **Show diff before committing** — always review with Mike
6. **Push + PR** — no merging without approval
7. **After code change**: `systemctl restart openclaw`
8. **Verify**: `journalctl -u openclaw -n 15 --no-pager`
9. **Health check**: `curl -s http://localhost:8340/`
10. **Write ops trace** in `docs/ops/traces/` in this monorepo for every VPS change

---

## PLC / Factory IO — Modbus Address Map

### Coils (Boolean I/O)

| Address | Name | Description |
|---------|------|-------------|
| 0 | motor_running | Motor run status |
| 1 | motor_stopped | Motor stop status |
| 2 | fault_alarm | Active fault indicator |
| 3 | conveyor_running | Conveyor run status |
| 4 | sensor_1 | Photoelectric sensor 1 |
| 5 | sensor_2 | Photoelectric sensor 2 |
| 6 | e_stop | Emergency stop (# SAFETY — never write without approval) |

### Holding Registers (Analog Values)

| Address | Name | Scale | Description |
|---------|------|-------|-------------|
| 100 | motor_speed | raw | Motor speed (0-100) |
| 101 | motor_current | ÷10 | Motor current (25 = 2.5A) |
| 102 | temperature | ÷10 | Temperature (650 = 65.0°C) |
| 103 | pressure | raw | Pneumatic pressure PSI |
| 104 | conveyor_speed | raw | Conveyor speed (0-100) |
| 105 | error_code | raw | 0=none, 1=overload, 2=sensor, 3=comms, 4=overheat, 5=low_press, 6=jam, 7=estop |

### Safety Rules for PLC Code

- **NEVER** write to coil 6 (e_stop) without explicit approval in the current session
- All generated Structured Text must include an e_stop check before any motion command
- Use Micro 820 compatible types only (BOOL, INT, REAL, DINT)
- Scale factors: motor_current ÷10, temperature ÷10

### MCP Servers Available

| Server | Command | Tools |
|--------|---------|-------|
| factorylm-brain | `python -m services.mcp.brain_server` | brain_search, brain_capture, brain_research, brain_ingest_file, brain_stats |
| factorylm-gist | `python -m services.mcp.gist_server` | gist management |
| factorylm-factory | `python -m services.mcp.factory_server` | factory_read_state, factory_inject_fault, factory_list_scenarios, factory_clear_faults, factory_write_coil, factory_write_register, factory_watch_tags, factory_connection_info |

### Arrested Development Phase

**Active until further notice.** See `.planning/ARRESTED_DEVELOPMENT.md`.
No new features. Every session: "Does this build the foundation or add to it?"
