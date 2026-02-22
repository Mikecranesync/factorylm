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
