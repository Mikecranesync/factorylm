# TRC-2026-02-16-001: Photo handler fix — Telegram message length + crash isolation

| Field | Value |
|-------|-------|
| **ID** | TRC-2026-02-16-001 |
| **Date** | 2026-02-16 |
| **Author** | hharp + Claude Opus 4.6 |
| **Duration** | ~1h |
| **Type** | fix |
| **Services** | plc-copilot |
| **Devices** | vps |
| **Trigger** | "Message is too long" error when Gemini returned verbose photo analysis responses |

---

## Context

The PLC Copilot Telegram bot (`photo_to_cmms_bot.py`) was crashing when users sent photos of industrial equipment. Gemini Vision returned detailed analysis responses that exceeded Telegram's 4096 character message limit. Additionally, unhandled exceptions in message handlers could crash the entire bot process.

## What Happened

1. Identified root cause: Gemini responses were exceeding Telegram's 4096-char message limit, causing `telegram.error.BadRequest: Message is too long`
2. No exception isolation existed — a failure in any handler would propagate and could crash the bot
3. Implemented multi-layer fix:
   - Added `_chunk_text()` helper that splits long text on paragraph breaks, then line breaks, then hard cut at 4096 chars
   - Added `send_long()` and `edit_long()` wrappers that chunk before sending
   - Added triple fallback on send: Markdown parse mode → plain text → error message
   - Wrapped all handlers in try/except with `log.exception()` for full tracebacks
   - Updated Gemini prompt to request responses under 2000 chars with structured format
   - Added hard truncation safety net at 3500 chars before any send

## Changes Made

| File/Config | Before | After | Why |
|-------------|--------|-------|-----|
| `services/plc-copilot/photo_to_cmms_bot.py` | Direct `message.reply_text()` calls | `send_long()`/`edit_long()` with chunking | Prevent Telegram 4096-char limit errors |
| Same file | No `_chunk_text` helper | `_chunk_text()` splits on paragraph → line → hard cut | Intelligent splitting preserves readability |
| Same file | No send fallback | Markdown → plain text → error message triple fallback | Graceful degradation on parse errors |
| Same file | Bare handlers, no try/except | All handlers wrapped in try/except + `log.exception()` | Prevent single handler crash from killing bot |
| Same file | No length guidance in Gemini prompt | Prompt requests <2000 chars, structured format | Reduce likelihood of overlength responses |
| Same file | No truncation safety | 3500-char hard truncation before send | Belt-and-suspenders safety net |

## Outcome

- Bot handles arbitrarily long Gemini responses without crashing
- Individual handler failures are logged but don't kill the bot process
- 220 insertions, 111 deletions (net +109 lines)
- Deployed to VPS immediately after fix

## Queryable Tags

- **error-codes**: `telegram.error.BadRequest: Message is too long`
- **root-cause**: Gemini responses exceed Telegram 4096-char message limit, no exception isolation in handlers
- **config-keys**: TELEGRAM_BOT_TOKEN, GEMINI_API_KEY
- **ports**: none (Telegram polling, no server port)
- **dependencies**: python-telegram-bot, google-generativeai

## Related

- **Workflows**: [WF-001](../workflows/deploy-plc-copilot.md)
- **Config Snapshots**: [2026-02-16_plc-copilot.yaml](../config-snapshots/2026-02-16_plc-copilot.yaml)
- **Commits**: `4adac30` — `fix: Handle long photo analysis responses + prevent handler crashes`
- **Rollback**: `git tag pre-photo-fix-*` if exists, otherwise `git revert 4adac30`
