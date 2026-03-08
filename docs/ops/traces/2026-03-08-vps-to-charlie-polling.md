# Ops Trace: VPS → CHARLIE Telegram Polling Migration

**Date:** 2026-03-08
**Author:** Claude (Travel Laptop)
**Status:** Deployed — @Tony_Macaroni_bot polling on CHARLIE

---

## What Changed

### Architecture Decision
Deployed troubleshoot Telegram bot on CHARLIE Mac Mini (100.82.246.52) using polling mode.
OpenClaw on VPS (100.68.120.99) remains running — used for VPS file retrieval and other tasks.

### Approach
- Used the **MACARONI** bot token (@Tony_Macaroni_bot) for CHARLIE — separate from OpenClaw's main token
- No bot token conflict — both bots run independently
- `services/troubleshoot/adapters/telegram_bot.py` uses `app.run_polling()` — no public endpoint needed
- LLM provider: Groq (free tier) via `LLM_PROVIDER=groq`

### Why
- Troubleshoot engine needs to run close to PLC data (local network)
- Polling mode requires no public endpoint, no Cloudflare, no reverse proxy
- ~1s latency from polling is invisible to technicians
- OpenClaw stays on VPS for data retrieval, no disruption

### Files Modified
| File | Change |
|------|--------|
| `CLUSTER.md` | Added Telegram polling note under CHARLIE node |
| `docs/ENDPOINT_MAP.md` | Deprecated `[GW-MSG]` :8340, added `[TG-POLL]` CHARLIE entry |
| `apps/mission-control/backend/main.py` | Commented out VPS from JARVIS_NODES |
| `infra/migration/progress.md` | Added Telegram polling migration checklist |
| `C:\Users\hharp\.claude\CLAUDE.md` | Updated infrastructure diagram: VPS → CHARLIE |

### No Code Changes Needed
`telegram_bot.py` line 181 already calls `app.run_polling(drop_pending_updates=True)`.

---

## Deployment Details

**Bot:** @Tony_Macaroni_bot (MACARONI token)
**Host:** CHARLIE Mac Mini (100.82.246.52)
**PID:** 29321
**Log:** `/tmp/telegram-bot.log`
**Workflows loaded:** mechanical_bolted_joint, photo_triage

### Start command (for restarts)
```bash
ssh charlienode@100.82.246.52 'cd ~/factorylm/services/troubleshoot && \
  TELEGRAM_TOKEN="8760221174:AAFADxGkL71U_X8NoWLrY6htsg7awOFfxHE" \
  GROQ_API_KEY="<from-doppler>" \
  LLM_PROVIDER=groq \
  nohup python3 -m adapters.telegram_bot > /tmp/telegram-bot.log 2>&1 &'
```

### Verify
```bash
ssh charlienode@100.82.246.52 "ps aux | grep telegram_bot | grep -v grep"
ssh charlienode@100.82.246.52 "tail -20 /tmp/telegram-bot.log"
```

---

## Risks
1. **CHARLIE offline = no troubleshoot bot** — Mac Mini must stay powered on and connected
2. **Process not daemonized** — runs via nohup, will die on reboot. Consider systemd/launchd later.
3. **Groq free tier limits** — may hit rate limits under heavy use
