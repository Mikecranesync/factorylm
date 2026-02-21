# Ops Trace: Jarvis Telegram Bot Deployment

**Date:** 2026-02-20 12:40 UTC
**Operator:** Claude Code
**VPS:** 100.68.120.99 (factorylm-prod)

## What Changed

Deployed new `jarvis-telegram` service to `/opt/jarvis-telegram/` on the VPS.

## Actions Taken

1. `scp -r services/jarvis-telegram root@100.68.120.99:/opt/jarvis-telegram`
2. Created venv: `python3 -m venv /opt/jarvis-telegram/venv`
3. Installed deps: `pip install -r requirements.txt`
4. Created `/opt/jarvis-telegram/.env` with:
   - `TELEGRAM_BOT_TOKEN` — @JarvisTLaptop_bot
   - `TELEGRAM_ALLOWED_USERS` — 8445149012
   - `GEMINI_API_KEY` — from existing VPS config
   - `MACHINE_NAME` — jarvis-vps
5. Installed systemd service: `/etc/systemd/system/jarvis-telegram.service`
6. `systemctl enable --now jarvis-telegram`

## Fix Applied During Deploy

Initial startup failed with `ImportError: attempted relative import beyond top-level package`.
All `from ..module` imports in handlers/ and integrations/ changed to absolute imports
(`from prompts import ...`, `from integrations.claude_bridge import ...`).

## Verification

- `systemctl status jarvis-telegram` — active (running)
- `journalctl -u jarvis-telegram` — clean startup, Gemini enabled, Claude CLI found (v2.1.29)
- `curl http://localhost:8081/health` — `{"status": "ok", "service": "jarvis-telegram"}`
- Telegram API getMe/getUpdates — 200 OK

## Services on VPS After

| Service | Status | Notes |
|---------|--------|-------|
| openclaw | active | Main bot |
| friday-telegram | active | FRIDAY bot |
| jarvis-telegram | active | NEW — Jarvis unified bot |
| master-of-puppets | active | Celery worker |
| plc-copilot | failed | Pre-existing failure |

## Rollback

```bash
systemctl stop jarvis-telegram
systemctl disable jarvis-telegram
rm /etc/systemd/system/jarvis-telegram.service
rm -rf /opt/jarvis-telegram
systemctl daemon-reload
```
