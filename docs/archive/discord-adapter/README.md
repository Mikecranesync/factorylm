# Archived: Discord Adapter

**Originally at:** `services/discord-adapter/`
**Archived:** 2026-03-02

## What This Was

Lightweight Discord bot bridging to the OpenClaw gateway for the NVIDIA Cosmos Cookoff Discord. Provided slash commands for PLC diagnostics, live tag reading, and VFD conveyor control.

### Slash Commands

| Command | Description |
|---------|-------------|
| `/diagnose <fault>` | AI fault diagnosis via Cosmos Reason 2 (uses live PLC tags) |
| `/status` | FactoryLM network node health |
| `/tags` | Live PLC tag values from factory floor |
| `/conveyor forward/reverse/stop` | Direct conveyor belt control |
| `/conveyor speed <hz>` | Set conveyor speed (1-60 Hz) |

## Best Ideas to Steal

1. **Rich Discord embeds** (embeds.py) — Formatted output with confidence bars and color-coded status
2. **Scheduled reports** (tasks.py) — Daily health + progress reports, DST-aware scheduling
3. **Graceful degradation** — Falls back to text when embed building fails
4. **Live PLC tag integration** — Reads real tags for AI diagnosis context
5. **VFD control from chat** — Conveyor forward/reverse/stop/speed from slash commands

## Key Files

- `bot.py` — Main Discord bot with OpenClaw gateway bridge
- `channels.py` — Channel configuration and routing
- `embeds.py` — Rich embed builders for Cosmos insights and node health
- `tasks.py` — Background scheduled tasks
