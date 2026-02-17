# TRC-2026-02-17-001: Capability Discovery + DiagramSkill

| Field | Value |
|-------|-------|
| **ID** | TRC-2026-02-17-001 |
| **Date** | 2026-02-17 |
| **Author** | Claude Code (Travel Laptop) |
| **Duration** | ~45m |
| **Type** | feature-build |
| **Services** | openclaw |
| **Devices** | vps, travel-laptop |
| **Trigger** | Mike tested Jarvis on Telegram — "Can you generate a wiring diagram?" failed |

---

## Context

After KB integration (PR #2), Mike tested Jarvis and found it couldn't generate wiring diagrams. Mined GitHub history across all repos to check if this was a regression. Finding: wiring diagrams never existed in OpenClaw — this is a new capability to build. All building blocks were already present (KB with manual content, ASCII wiring docs on develop branch, LLM routing).

## What Happened

1. Explored OpenClaw git history — no diagram capabilities ever existed (8 branches, 30+ commits)
2. Explored factorylm-monorepo — found ASCII wiring diagram in `docs/demo-setup/conveyor-wiring-with-contactor.md` (develop branch)
3. Explored Clawdbot/Rivet-PRO repos — Rivet-PRO has mermaid parser, Clawdbot had no diagrams
4. Created `feat/jarvis-capability-discovery` branch from `feat/kb-maint-llm`
5. Added DIAGRAM intent, keyword patterns, DiagramSkill, LLM route
6. Added source_url to ChatSkill KB context
7. Updated system prompt with diagram + KB capabilities
8. Tested via API — wiring diagram generated with ASCII box-drawing art
9. Pushed branch, opened PR #3

## Changes Made

| File/Config | Before | After | Why |
|-------------|--------|-------|-----|
| `openclaw/types.py` | 10 intents | 11 intents (+DIAGRAM) | Route wiring requests |
| `openclaw/messages/intent.py` | No diagram keywords | wiring/diagram/schematic/blueprint/draw/circuit → DIAGRAM | Intent classification |
| `openclaw/llm/router.py` | No DIAGRAM route | DIAGRAM → openrouter, anthropic, groq | Route to best ASCII art provider |
| `openclaw/skills/builtin/diagram.py` | (new) | DiagramSkill with Micro820 I/O reference + format template | Generate wiring diagrams |
| `openclaw/skills/registry.py` | 8 skills | 9 skills (+diagram) | Register new skill |
| `openclaw/skills/builtin/chat.py` | No source_url | Includes source_url from KB atoms | Link to manuals |
| `openclaw/llm/prompts.py` | No diagram mention | Lists diagram + KB capabilities | LLM knows it can draw |

## Outcome

- Branch `feat/jarvis-capability-discovery` pushed with 3 commits
- PR #3 opened: https://github.com/Mikecranesync/openclaw/pull/3
- DiagramSkill tested and working via API
- Currently live on VPS for Telegram testing
- **NOT deployed to stable** — Mike reviews and deploys

## Queryable Tags

- **capabilities**: diagram, wiring, schematic
- **intents**: DIAGRAM
- **skills**: diagram
- **routes**: openrouter → anthropic → groq

## Related

- **PR**: https://github.com/Mikecranesync/openclaw/pull/3
- **Depends on**: PR #2 (feat/kb-maint-llm)
- **Commits**: `e1c4c23`, `43603f9`, `0398fbd`
- **Prior Traces**: [TRC-2026-02-16-005](./2026-02-16_kb-maint-llm-wiring.md)
