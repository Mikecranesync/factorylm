# Ops Trace: Jarvis UX + Layer 0 Improvements

**Date:** 2026-02-17
**Branch:** `feat/jarvis-ux-and-layer0`
**VPS Commits:** `6f07f5f`, `bd359a4`, `a7e0411`, `1c17244`, `e7b507b` (merge)

## What Changed

Two high-impact improvements aligned with the FactoryLM 4-layer vision:

1. **Fix Intent Routing + Conversation Memory** — stop greedy patterns from misrouting casual questions; give Jarvis memory within conversations
2. **KB-First Routing + Source Attribution** — return KB answers directly (Layer 0 short-circuit) when confidence is high; always cite sources deterministically

### Files Modified (4)

| File | Change |
|------|--------|
| `openclaw/messages/intent.py` | Split greedy DIAGNOSE regex into contextual patterns; removed ambiguous "current" from STATUS, "repair" from WORK_ORDER |
| `openclaw/gateway/telegram.py` | Per-user in-memory conversation history (10 msgs, 30min TTL); typing indicator; registered 12 missing command handlers; /clear command |
| `openclaw/skills/builtin/chat.py` | Layer 0 short-circuit for high-confidence procedural KB atoms; deterministic Sources block; conversation history to LLM |
| `openclaw/skills/builtin/diagnose.py` | Layer 0 logic gates for E001/M001/M002/T001/C001; source_url extraction from KB; deterministic Sources block; conversation history |

### Merge

Merged `feat/gist-project-skills` to bring in GIST/PROJECT Intent enum values, LLM routes, skill files, and registry entries needed by intent.py on this branch. Resolved conflict in intent.py keeping the improved less-greedy patterns.

## Intent Routing Changes

### Before (greedy)
| Input | Old Intent | Problem |
|-------|-----------|---------|
| "why is the sky blue?" | DIAGNOSE | "why" matched |
| "the error in my code" | DIAGNOSE | "error" matched |
| "currently reading docs" | STATUS | "current" matched |
| "how to repair a bike?" | WORK_ORDER | "repair" matched |

### After (contextual)
| Input | New Intent | Why |
|-------|-----------|-----|
| "why is the sky blue?" | CHAT | "why" requires fault/equipment context within 30 chars |
| "the error in my code" | CHAT | "error" requires equipment noun nearby |
| "why is the motor down?" | DIAGNOSE | "why" + "down" with equipment context |
| "fault alarm on line 3" | DIAGNOSE | "fault" and "alarm" always match |
| "currently reading docs" | CHAT | "current" removed from STATUS |
| "how to repair a bike?" | CHAT | "repair" removed from WORK_ORDER |

## Layer 0 Logic

### ChatSkill
- KB search returns atoms with `atom_type`, `score`, `steps`, `fixes`, `source_url`
- If atom type is procedural (`procedure`, `fault_code`, `checklist`, `troubleshooting`) AND has steps/fixes AND score > 0.85: return directly tagged `_Layer 0 (KB direct) | 0ms_`
- All other responses get deterministic `**Sources:**` block appended

### DiagnoseSkill
- Same KB enrichment pattern as ChatSkill but per-fault-code
- Layer 0 eligible fault codes: E001, M001, M002, T001, C001
- Must also be actionable type with steps or fixes
- Layer 0 response includes fault summary header + KB answer + sources
- LLM path also gets sources appended deterministically

## Conversation Memory

- `telegram.py` maintains `dict[user_id, list[dict]]` with 10-message cap and 30-minute TTL
- Each message stores `{"role": "user"|"assistant", "content": "...", "ts": float}`
- History injected via `InboundMessage.metadata["history"]`
- Both ChatSkill and DiagnoseSkill pass history as message prefix to LLM
- `/clear` command flushes user's history

## Telegram Fixes

- Registered `CommandHandler` for: status, diagnose, health, search, run, diagram, wiring, gist, project, wo, workorder, admin, photo
- Previously these `/commands` were silently dropped (TEXT handler uses `~filters.COMMAND`)
- Added `ChatAction.TYPING` before skill dispatch for perceived speed

## Verification

- 11 skills registered in journalctl (diagnose, status, photo, work_order, admin, search, shell, diagram, chat, gist, project)
- Health check: `curl localhost:8340/` shows all skills + providers
- All Python files pass `ast.parse()` syntax check
- Branch pushed to `origin/feat/jarvis-ux-and-layer0`
