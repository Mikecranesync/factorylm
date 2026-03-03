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
