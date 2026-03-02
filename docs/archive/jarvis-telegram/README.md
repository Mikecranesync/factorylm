# Archived: Jarvis Telegram

**Originally at:** `services/jarvis-telegram/`
**Archived:** 2026-03-02

## What This Was

Unified Telegram bot combining three production implementations:

- **Puppeteer Bot** — Photo diagnosis (Gemini vision), voice commands, work order creation
- **Claude Bridge** — Routes text to Claude CLI subprocess
- **Management Dashboard** — `/status`, `/agents`, `/metrics` for ops monitoring

### Capabilities

| Feature | Command/Action |
|---------|---------------|
| Photo Diagnosis | Send a photo |
| Nameplate OCR | Tap "Nameplate Focus" button |
| Voice Commands | Send a voice note |
| Text Chat (Claude) | Send text message |
| Work Order Creation | Tap "Create Work Order" or `/wo` |
| System Status | `/status` |
| Agent Roster | `/agents` |

## Best Ideas to Steal

1. **Claude CLI bridge** (integrations/claude_bridge.py) — Routes messages to `claude` subprocess, captures output
2. **Groq/Gemini vision** (integrations/) — Fast fault diagnosis from photos
3. **CMMS work orders** (handlers/photo.py) — Photo → structured maintenance request
4. **Handler modularity** — Clean separation of photo/voice/text handlers with shared conversation state
5. **Rate limiting + security** (config.py) — Built-in rate limiting and allowed-user lists

## Key Files

```
bot.py                    # Entry point, handler registration
config.py                 # TelegramConfig (Pydantic validated)
conversation.py           # ConversationManager (multi-turn sessions)
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
