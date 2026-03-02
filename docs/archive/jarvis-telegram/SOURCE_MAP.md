# Source Map — jarvis-telegram

All code restored from `jarvis-workspace` repository (backup at `~/resurrection-yard/jarvis-workspace/`).

| New File | Source Branch | Source Path | Lines |
|----------|--------------|-------------|-------|
| `config.py` | `feature/factorylm-remote` | `infrastructure/bot/config.py` | 145 |
| `conversation.py` | `feature/factorylm-remote` | `infrastructure/bot/conversation_manager.py` | 400 |
| `prompts.py` | `feature/rideview-continuous-improvement` | `projects/factorylm/puppeteer/bot.py` (prompt constants) | — |
| `handlers/photo.py` | `feature/rideview-continuous-improvement` | `projects/factorylm/puppeteer/bot.py` (photo/callback handlers) | — |
| `handlers/voice.py` | `feature/rideview-continuous-improvement` | `projects/factorylm/puppeteer/bot.py` (voice handler) | — |
| `handlers/text.py` | `main` | `installers/claude-telegram-bridge/claude_telegram_bridge.py` | 274 |
| `handlers/management.py` | `feature/factorylm-remote` | `infrastructure/bot/management_handlers.py` | 359 |
| `integrations/gemini.py` | `feature/rideview-continuous-improvement` | `projects/factorylm/puppeteer/bot.py` (Gemini client) | — |
| `integrations/cmms.py` | `feature/rideview-continuous-improvement` | `projects/factorylm/puppeteer/bot.py` (CMSClient class) | — |
| `integrations/claude_bridge.py` | `main` | `installers/claude-telegram-bridge/claude_telegram_bridge.py` (run_claude fn) | — |

## Original Implementations

| Bot | Branch | File | Lines | Capabilities |
|-----|--------|------|-------|-------------|
| Puppeteer Bot | `feature/rideview-continuous-improvement` | `projects/factorylm/puppeteer/bot.py` | 554 | Photo diagnosis, voice, work orders, inline buttons |
| Claude Bridge | `main` | `installers/claude-telegram-bridge/claude_telegram_bridge.py` | 274 | Text → Claude CLI subprocess |
| Management Dashboard | `feature/factorylm-remote` | `infrastructure/bot/management_handlers.py` | 359 | /status, /agents, /metrics |
