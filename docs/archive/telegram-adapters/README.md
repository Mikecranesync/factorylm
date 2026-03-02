# Archived: Telegram Adapters

**Originally at:** `services/telegram/`
**Archived:** 2026-03-02

## What This Was

Multi-bot Telegram integration framework with three distinct personalities:

- **Gus** (`factorylm_bot.py`) — Factory floor Telegram bot with AI-powered equipment diagnosis, background fault polling every 5s, and proactive alerts
- **Friday** (`telegram_router.py`) — Multi-node sticky routing assistant (`/on plc`, `/on travel`, `/plc ls`) that forwards commands to the correct cluster node
- **IO Adapter** (`io_adapter.py`) — HTTP-based PLC reader that hits any REST API for tag values — not tied to Modbus directly

## Best Ideas to Steal

1. **HTTP gateway pattern** (io_adapter.py) — Abstracts PLC access behind HTTP, so any adapter can read tags without knowing the protocol
2. **Multi-node routing** (telegram_router.py) — Per-chat sticky node selection with `/on <node>` command
3. **Background fault polling** (factorylm_bot.py) — 5-second poll loop with proactive Telegram alerts on state change
4. **RemoteMe** (jarvis_mio/) — AI remote control concept via Telegram long-polling

## Key Files

- `factorylm_bot.py` — Main bot entry point
- `io_adapter.py` — HTTP PLC reader module
- `telegram_router.py` — Multi-node routing layer
- `jarvis_mio/remoteme/` — RemoteMe backend + poll forwarder
