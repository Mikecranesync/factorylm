# Jarvis Telegram Bot

Unified Telegram bot combining three production implementations from `jarvis-workspace`:

- **Puppeteer Bot** — Photo diagnosis (Gemini vision), voice commands, work order creation
- **Claude Bridge** — Routes text to Claude CLI subprocess
- **Management Dashboard** — /status, /agents, /metrics for ops monitoring

## Quick Start

```bash
cd services/jarvis-telegram
cp .env.example .env
# Fill in TELEGRAM_BOT_TOKEN and other values

pip install -r requirements.txt
python bot.py
```

## Capabilities

| # | Feature | Command/Action |
|---|---------|---------------|
| 1 | Photo Diagnosis | Send a photo |
| 2 | Nameplate OCR | Tap "Nameplate Focus" button |
| 3 | Voice Commands | Send a voice note |
| 4 | Text Chat (Claude) | Send text message |
| 5 | Work Order Creation | Tap "Create Work Order" or `/wo` |
| 6 | Re-analyze Photo | Tap "Re-analyze" button |
| 7 | Session History | `/history` |
| 8 | System Status | `/status` |
| 9 | Agent Roster | `/agents` |
| 10 | Performance Metrics | `/metrics` |
| 11 | Clear Conversation | `/clear` |

## Deployment (VPS)

```bash
# Copy to VPS
scp -r services/jarvis-telegram root@100.68.120.99:/opt/jarvis-telegram/

# Install
ssh root@100.68.120.99
cd /opt/jarvis-telegram
pip install -r requirements.txt
cp .env.example .env && nano .env

# Systemd
cp systemd/jarvis-telegram.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now jarvis-telegram
journalctl -u jarvis-telegram -f
```

## Architecture

```
bot.py                    # Entry point, handler registration, health check
config.py                 # TelegramConfig (Pydantic validated)
conversation.py           # ConversationManager (multi-turn sessions)
prompts.py                # AI prompts (diagnosis, voice, work order)
handlers/
  photo.py                # Photo analysis + inline action buttons
  voice.py                # Voice note processing
  text.py                 # Text → Claude CLI or Gemini
  management.py           # /status, /agents, /metrics
integrations/
  gemini.py               # Gemini 2.5 Flash vision client
  cmms.py                 # Atlas CMMS work order client
  claude_bridge.py        # Claude CLI subprocess bridge
```

See `SOURCE_MAP.md` for provenance of each file.
