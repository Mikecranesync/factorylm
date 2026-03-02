# Archived: FactoryLM Discord Layer

**Originally at:** `services/factorylm-discord-layer/`
**Archived:** 2026-03-02

## What This Was

Production Discord relay daemon for agent swarm coordination. HTTP server (:8765) that receives messages from agents and posts them to Discord channels via webhooks.

Features: TOML config, token-bucket rate limiting, Telegram↔Discord format bridging, automated channel/webhook provisioning, guild slash commands for fleet management.

## Best Ideas to Steal

1. **Agent fleet management** (bot/commands.py) — `/relay`, `/status`, `/config`, `/fleet` slash commands
2. **Format bridging** (relay/bridge.py) — Telegram markdown → Discord embed converter with truncation
3. **Rate limiting** (relay/rate_limiter.py) — Token bucket with queue management
4. **Setup automation** (setup/) — Channel/webhook provisioning from config

## Key Files

- `config.py` — TOML config loader with env var overrides
- `bot/commands.py` — Guild slash commands
- `relay/bridge.py` — Message format converter
- `relay/rate_limiter.py` — Rate limiter
- `setup/discord_setup.py` — Channel provisioning
