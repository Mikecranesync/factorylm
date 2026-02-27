# CLAUDE.md — factorylm-discord-layer

## What This Is

Discord communication layer for the FactoryLM agent swarm. Provides:
- Discord server setup automation (channels, webhooks)
- HTTP relay daemon for agent → Discord webhook posting
- Rate-limited webhook delivery with queue management
- Telegram ↔ Discord message format bridge
- Bot slash commands for fleet monitoring

## Directory Layout

```
src/factorylm/
├── models.py          # Pydantic v2 config models
├── config.py          # TOML loader (tomli)
├── setup/
│   ├── discord_setup.py   # Channel/webhook provisioning
│   └── config_writer.py   # Write config.toml
├── relay/
│   ├── daemon.py          # aiohttp relay server (:8765)
│   ├── rate_limiter.py    # Token bucket + queue
│   └── bridge.py          # Telegram↔Discord format
└── bot/
    ├── commands.py        # Slash commands
    └── events.py          # on_ready, error handling
```

## Coding Standards

- **Python**: 3.10+
- **Linter**: `ruff check src/ tests/`
- **Formatter**: `ruff format src/ tests/`
- **Tests**: `pytest tests/ -v` with `pytest-asyncio`
- **Models**: Pydantic v2 (`BaseModel`, not dataclass)
- **Async**: `aiohttp` for HTTP server and client
- **Config**: TOML via `tomli`, never store secrets in files

## Branch Naming

- `chore/scaffold` — project setup
- `feature/<name>` — new functionality
- `docs/<name>` — documentation only

## Commit Format

```
feat(scope): description
fix(scope): description
chore(scope): description
docs(scope): description
```

## Security Rules

- Bot tokens read from env var named in config, NEVER stored in config files
- Webhook URLs treated as secrets — never logged, never in /config show
- Relay daemon binds 127.0.0.1 by default (Tailscale IP for remote)
- Guild commands only (not global) to limit blast radius

## Entry Points

- `factorylm-setup` → `factorylm.setup.discord_setup:cli_main`
- `factorylm-relay` → `factorylm.relay.daemon:cli_main`
- `factorylm-bot` → `factorylm.bot.commands:cli_main`
