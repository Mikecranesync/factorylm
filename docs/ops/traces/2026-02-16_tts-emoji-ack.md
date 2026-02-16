# TRC-2026-02-16-003: TTS Voice Replies + Emoji Ack + Rich Formatting

| Field | Value |
|-------|-------|
| **ID** | TRC-2026-02-16-003 |
| **Date** | 2026-02-16 |
| **Author** | Claude (Travel Laptop) |
| **Duration** | ~20m |
| **Type** | feature-build |
| **Services** | openclaw |
| **Devices** | vps, travel-laptop |
| **Trigger** | Plan to restore old Jarvis rich behaviors (TTS, ack, formatting) |

---

## Context

OpenClaw (Jarvis) was text-in/text-out only. Old Jarvis had voice notes (Edge TTS, Jenny voice), emoji reactions on receipt, and rich formatted responses with emoji headers and code blocks. Voice STT (inbound) was already shipped. This adds voice TTS (outbound) + ack + formatting.

## What Happened

1. Committed 5 existing modified files on VPS (Jarvis identity, routing, voice STT, chunking) — `8dce07d`
2. Created `feat/tts-emoji-ack` branch
3. Installed `edge-tts` in VPS venv (pure Python, free, uses Microsoft Edge TTS API)
4. Modified `telegram.py`: added `_ack()` (👀 reaction), `_text_to_speech()`, `_reply_voice()`, `_strip_markdown()` helper
5. Modified `prompts.py`: updated communication style with emoji headers, bold, code blocks, status emojis
6. Created `CLAUDE.md` on VPS with git/ops rules
7. Updated local `CLAUDE.md` with VPS Change Protocol section
8. Committed, pushed branch, restarted service — clean startup confirmed

## Changes Made

| File/Config | Before | After | Why |
|-------------|--------|-------|-----|
| `openclaw/gateway/telegram.py` | Text-only replies | +TTS voice notes, +👀 ack reaction | Restore old Jarvis UX |
| `openclaw/llm/prompts.py` | "Direct and professional" style | Emoji headers, bold tags, code blocks | Match old Jarvis formatting |
| `CLAUDE.md` (VPS) | Did not exist | Git workflow + ops rules | Encode rules for future sessions |
| `CLAUDE.md` (monorepo) | No VPS section | +VPS Change Protocol | Remote ops instructions |

## Outcome

- Service running on VPS, health check OK
- Branch `feat/tts-emoji-ack` pushed to `origin`
- New dep: `edge-tts` (en-US-JennyNeural voice, zero cost)
- PR pending creation and approval before merge

## Queryable Tags

- **root-cause**: missing-feature (TTS + ack stripped during OpenClaw migration)
- **dependencies**: edge-tts
- **ports**: 8340
- **config-keys**: TTS_VOICE, TTS_MAX_CHARS, TTS_MIN_CHARS

## Related

- **Prior Traces**: [TRC-2026-02-16-001](./2026-02-16_jarvis-soul-restore.md)
- **Commits**: `85949ac` (feat branch), `8dce07d` (prior commit)
- **Branch**: `feat/tts-emoji-ack` on `Mikecranesync/openclaw`
