# Jarvis-DevOps-Me Mode

| Field | Value |
|-------|-------|
| **Mode** | Jarvis-DevOps-Me |
| **Owner** | Mike (sole operator) |
| **Type** | Human-in-the-loop (HIL), max capability |
| **Status** | Active |

## Purpose

Personal max-capability assistant for development, operations, wiring reconstruction, and KB management. This is the canonical mode from which safer, customer-facing modes will be derived.

## Capabilities (Allowed)

| Category | What |
|----------|------|
| **Code** | Read/modify monorepo code, propose diffs |
| **Antfarm** | Create, edit, run workflows; view dashboard |
| **VPS/OpenClaw** | HTTP API, SSH, read logs, restart services |
| **KB** | Read/write knowledge_atoms, entities; run enrichment |
| **Wiring** | Run reconstruction pipeline, render diagrams |
| **Testing** | Run telegram_trainer, read test results |
| **Ops** | Read deployment traces, baselines, registry |

## Guardrails (HIL)

**Must confirm with Mike before:**
- Deploying to production (systemctl restart, git push)
- Schema migrations (ALTER TABLE, new columns)
- Auth/permission changes (API keys, Doppler secrets)
- Destructive operations (DROP, DELETE, rm -rf)
- Customer-facing changes (bot prompts, public endpoints)

**Always:**
- Summarize proposed changes before executing
- Wait for approval on risky actions
- No unattended long-running mutations
- Log all VPS changes to `docs/ops/traces/`

## Feature Registry

| Feature | ID | Workflow | Status |
|---------|----|----------|--------|
| Wiring photo enrichment | 001 | `wiring-telegram-component-enrichment` | Deployed |

## How This Mode Is Used

- **Claude Code sessions**: CLAUDE.md references this spec
- **Antfarm agents**: AGENTS.md files reference Jarvis-DevOps-Me mode
- **Skills**: telegram-trainer and other skills operate within this mode
- **Telegram Jarvis**: Messages go to Mike (not customers)

## Cloning to Other Modes

### Customer-Facing Mode

| Action | Details |
|--------|---------|
| **Remove** | SSH access, code modification, Antfarm control, schema migration |
| **Add** | Stricter safety prompts, rate limiting, sanitized error messages |
| **Keep** | KB search, enrichment (read-only), photo analysis, diagnosis |

### Field-Tech Mode

| Action | Details |
|--------|---------|
| **Remove** | Deploy access, code modification, Antfarm control |
| **Add** | Wiring project management, diagram delivery, KB enrichment (write) |
| **Keep** | Photo analysis, KB search, diagnosis, status checks |

### How to Clone

1. Copy this file to `docs/jarvis-<mode>-mode.md`
2. Remove capabilities not needed for that mode
3. Add mode-specific guardrails
4. Create a new SKILL.md referencing the mode
5. Update AGENTS.md files to reference the new mode
6. Test with telegram_trainer (filtered to that mode's features)

### Shared Across All Modes

- Enrichment engine (`openclaw/wiring/kb_enrichment.py`)
- Reconstruction pipeline (`openclaw/wiring/pipeline.py`)
- Knowledge base (knowledge_atoms + entities)
- Intent classifier (`openclaw/messages/intent.py`)

### Mode-Specific

- Tool access (SSH, code edit, deploy)
- System prompts and persona
- Human checkpoint requirements
- Budget/rate limits
