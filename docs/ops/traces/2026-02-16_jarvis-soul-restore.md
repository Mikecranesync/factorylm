# TRC-2026-02-16-001: Restore Jarvis Soul into Python OpenClaw

| Field | Value |
|-------|-------|
| **ID** | TRC-2026-02-16-001 |
| **Date** | 2026-02-16 |
| **Author** | Claude Code |
| **Duration** | 0h 10m |
| **Type** | config-change |
| **Services** | openclaw |
| **Devices** | vps |
| **Trigger** | OpenClaw running with generic identity and "Message is too long" bug |

---

## Context

Python OpenClaw replaced the old Node.js Jarvis on the VPS. It was running with:
- Generic "OpenClaw" system prompt (no Jarvis personality)
- Only `groq` + `gemini` providers active
- "Message is too long" crashes on photo analysis
- No Anthropic routing for high-value intents
- No matrix/jarvis connectors configured

## What Happened

1. Read all 7 target files on VPS via SSH to understand current state
2. Ported `_chunk_text()` helper from PLC Copilot (`photo_to_cmms_bot.py`) into `telegram.py`
3. Updated `_reply()` method with chunking + triple fallback (Markdown -> plain -> error)
4. Updated `send()` method to also chunk outbound messages
5. Updated `_on_photo()` with better error handling for photo download failures
6. Replaced generic system prompt in `prompts.py` with Jarvis identity
7. Updated `router.py` routing table: Anthropic primary for DIAGNOSE/WORK_ORDER, Groq for all else
8. Added `anthropic_daily_request_limit` and `anthropic_daily_token_limit` to `config.py`
9. Wired Anthropic budget tracking in `app.py`, added `/budget` endpoint
10. Updated `openclaw.yaml` with Anthropic config, matrix_url, jarvis_hosts
11. Restarted service — clean startup, no errors

## Changes Made

| File/Config | Before | After | Why |
|-------------|--------|-------|-----|
| `telegram.py` | No chunking, crashes on >4096 char responses | `_chunk_text()` + chunked `_reply()` | Fix "Message is too long" crash |
| `prompts.py` | Generic "OpenClaw" prompt | Jarvis personality with industrial focus | Restore Jarvis identity |
| `router.py` | DIAGNOSE/WORK_ORDER -> openrouter (not available) | DIAGNOSE/WORK_ORDER -> anthropic (with groq fallback) | Route high-value intents to Claude |
| `config.py` | No anthropic budget fields | `anthropic_daily_request_limit=100`, `anthropic_daily_token_limit=100000` | Budget guardrails |
| `app.py` | No anthropic budget config | Anthropic budget wired, `/budget` endpoint added | Enforce limits, monitor usage |
| `openclaw.yaml` | Empty matrix_url, no jarvis_hosts | matrix_url, jarvis_hosts, anthropic config | Enable connectors, set limits |

## Outcome

- OpenClaw running as "Jarvis (OpenClaw)" with correct personality
- Providers active: groq, gemini (anthropic activates when key added to Doppler)
- Connectors: matrix, jarvis now configured
- All 7 skills registered
- Telegram adapter started with message chunking
- No errors in startup logs
- `/budget` endpoint available for monitoring

## Queryable Tags

- **error-codes**: "Message is too long" (Telegram API 400)
- **root-cause**: Missing message chunking in Telegram adapter
- **config-keys**: ANTHROPIC_API_KEY, anthropic_daily_request_limit, anthropic_daily_token_limit
- **ports**: 8340
- **dependencies**: python-telegram-bot, anthropic

## Related

- **Workflows**: [WF-006](../workflows/restore-jarvis-openclaw.md)
- **Prior Traces**: [TRC-2026-02-16 photo-handler-fix](./2026-02-16_photo-handler-fix.md)
