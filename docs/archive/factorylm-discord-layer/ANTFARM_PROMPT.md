# ANTFARM_PROMPT — FactoryLM Discord Layer

> This is the original build specification. See PRD.md for structured requirements
> and CLAUDE.md for coding standards.

## Overview

Build a Discord communication layer for the FactoryLM agent swarm. 8 sequential stories,
each on its own branch with a PR. CI must be green before moving to the next story.

## Stories

1. **Scaffold** — Directory tree, CI, CLAUDE.md, PRD.md, pyproject.toml
2. **Config** — Pydantic v2 models, TOML loader, env-var token resolution
3. **Discord Setup** — Automated channel/webhook provisioning via Discord REST API
4. **Relay Daemon** — aiohttp server on :8765, POST /relay, GET /status, GET /health
5. **Rate Limiter** — Token bucket (5/2s per webhook), queue (500), drain worker
6. **Bridge** — Telegram↔Discord markdown conversion, truncation, embed builders
7. **Slash Commands** — /relay, /status, /config show, /fleet (guild-only)
8. **README** — Architecture diagram, setup guide, security notes

## Agents

| Agent | Channel | Machine |
|-------|---------|---------|
| Tony | #tony | Mac Mini (100.108.19.94) |
| Ultron | #ultron | DO VPS (100.68.120.99) |
| Jarvis | #jarvis | Travel Laptop (100.83.251.23) |
| Hetzner | #hetzner | Hetzner (100.67.25.53) |

## Channels

- FACTORY FLOOR category: #plc-live, #alerts
- AGENTS category: #tony, #ultron, #jarvis, #hetzner, #dispatch-log

## Relay

- Port 8765 (Mac Mini — no conflict with Jarvis Node on PLC Laptop)
- POST /relay: {agent, message, format} → webhook → 202
- GET /status: agent list, queue depths, uptime
- GET /health: {ok: true}

## Rate Limits

- Token bucket: 5 requests / 2 seconds per webhook URL
- Queue: asyncio.Queue(maxsize=500) per webhook
- Eviction: drop oldest, log WARNING
- Retry: 429 → backoff using X-RateLimit-Reset header

## Security

- Bot token: env var only, never in config file
- Webhook URLs: treated as secrets
- Relay: bind 127.0.0.1 or Tailscale IP
- Commands: guild-only, not global
