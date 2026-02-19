# Ops Trace: Deterministic Troubleshoot Engine

**Date:** 2026-02-19
**Author:** Claude (Opus 4.6)
**Branch:** feat/troubleshoot-engine
**Status:** Code ready, pending VPS deployment

## What Changed

Added a deterministic, flowchart-driven troubleshooting engine that walks technicians through step-by-step diagnosis via Telegram — zero LLM tokens on the happy path. This IS the Layer 0 vision: "convert Layer 3 answers into Layer 0 code."

## Files Created

| File | Purpose |
|------|---------|
| `openclaw/troubleshoot/__init__.py` | Package init, exports |
| `openclaw/troubleshoot/models.py` | TreeNode, TroubleshootTree, TroubleshootSession, TreeResponse dataclasses |
| `openclaw/troubleshoot/engine.py` | TreeRunner: session management, node traversal, answer matching, PLC auto-answer |
| `openclaw/troubleshoot/store.py` | DB operations: load_all_trees(), upsert_tree(), create_schema() |
| `openclaw/troubleshoot/skill.py` | TroubleshootSkill: handle(), format questions/resolutions, LLM handoff |
| `openclaw/troubleshoot/seed.py` | CLI: load JSON trees from trees/ dir into DB |
| `openclaw/troubleshoot/trees/estop-recovery.json` | E001: E-stop recovery (7 nodes) |
| `openclaw/troubleshoot/trees/motor-overcurrent.json` | M001: Motor overcurrent (10 nodes) |
| `openclaw/troubleshoot/trees/motor-stopped.json` | M002: Motor stopped unexpected (13 nodes) |
| `openclaw/troubleshoot/trees/conveyor-jam.json` | C001: Conveyor jam (9 nodes) |
| `openclaw/troubleshoot/trees/high-temperature.json` | T001: High temperature (9 nodes) |
| `openclaw/troubleshoot/trees/low-pressure.json` | P001: Low air pressure (7 nodes) |

## Files Modified

| File | Change |
|------|--------|
| `openclaw/types.py` | Added `TROUBLESHOOT = "TROUBLESHOOT"` to Intent enum |
| `openclaw/messages/intent.py` | Added TROUBLESHOOT patterns: troubleshoot, walk me through, step by step, guide me, how do i fix |
| `output/vps-patches/router.py` | Added `Intent.TROUBLESHOOT: Route("groq", ["deepseek", "openrouter"])` |
| `output/vps-patches/telegram.py` | Added "troubleshoot" to command handlers list |
| `output/vps-patches/diagnose.py` | Added `_maybe_offer_troubleshoot()` — after fault detection, offers guided walkthrough |

## VPS Deployment Steps

1. Copy `openclaw/troubleshoot/` to `/opt/openclaw/openclaw/troubleshoot/`
2. Apply patches from `output/vps-patches/` (router.py, telegram.py, diagnose.py)
3. Apply registry patch per `output/vps-patches/troubleshoot_registry_patch.py`
4. Run: `python -m openclaw.troubleshoot.seed` to create table + load 6 trees
5. `systemctl restart openclaw`
6. Verify: `journalctl -u openclaw -n 20 --no-pager` — should show "TroubleshootSkill registered with 6 trees"

## Key Design Decisions

- **Custom engine over external library**: ~250 lines total. Experta/business_rules_reasoning add deps without solving the problem.
- **Coaching tone**: Tree node text is authored in conversational style. Skill formatter adds transition phrases between nodes.
- **Session persistence**: JSON file at `/tmp/openclaw_troubleshoot_sessions.json` — survives restarts, 30-min TTL.
- **PLC auto-answer**: If a question node has `plc_tag` set and the PLC snapshot has that value, the engine auto-advances (e.g., skips "is the E-stop active?" if PLC data already says yes/no).
- **LLM handoff**: When user input doesn't match options OR a resolution node has `llm_handoff: true`, all accumulated context is passed to the LLM with a coaching-tone system prompt.
- **DiagnoseSkill escalation**: After fault detection, DiagnoseSkill checks if a troubleshoot tree exists for the fault and offers "Want me to walk you through it step by step?"

## Risk

- Session-aware dispatch in `app.py` is critical — without it, numeric replies ("2") to troubleshoot questions get classified as GENERAL intent and miss the active session. The patch in `troubleshoot_registry_patch.py` documents this.
