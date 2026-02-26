# Discord Adapter — FactoryLM

Bridges Discord to the OpenClaw gateway so Jarvis can respond in the NVIDIA Cosmos Cookoff Discord.

## Quick Start

```bash
pip install -r requirements.txt
DISCORD_BOT_TOKEN=xxx python bot.py
```

## Env Vars

| Var | Required | Default | Description |
|-----|----------|---------|-------------|
| `DISCORD_BOT_TOKEN` | ✅ | — | From Discord Developer Portal |
| `OPENCLAW_GATEWAY_URL` | No | `http://localhost:18800` | OpenClaw gateway endpoint |
| `DISCORD_MENTION_ONLY` | No | `true` | Only respond when @mentioned |
| `DISCORD_ALLOWED_CHANNELS` | No | — | Comma-separated channel IDs to respond in |
| `DISCORD_BOT_NAME` | No | `FactoryLM` | Display name in logs |
| `CONVEYOR_RELAY_URL` | No | `http://100.68.120.99:8400` | Conveyor relay on VPS |
| `MATRIX_API_URL` | No | `http://100.72.2.99:8001` | Matrix API for live PLC tag snapshots |

## Slash Commands

| Command | Description |
|---------|-------------|
| `/diagnose <fault>` | AI-powered fault diagnosis via Cosmos Reason 2 (uses live PLC tags when available) |
| `/status` | Check FactoryLM network node health |
| `/about` | What is FactoryLM? |
| `/tags` | Show live PLC tag values from the factory floor |
| `/conveyor forward` | Start conveyor belt forward |
| `/conveyor reverse` | Start conveyor belt in reverse |
| `/conveyor stop` | Stop the conveyor belt |
| `/conveyor speed <hz>` | Set conveyor speed (1-60 Hz) |
| `/conveyor status` | Show current conveyor state |
