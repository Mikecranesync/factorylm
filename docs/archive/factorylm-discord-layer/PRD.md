# PRD — FactoryLM Discord Layer

## Mission

Provide a clean, testable Discord communication layer for the FactoryLM agent swarm. Agents (Tony, Ultron, Jarvis, Hetzner) post to dedicated Discord channels via webhooks. A relay daemon manages rate limits and queuing. A bot provides slash commands for monitoring.

## Architecture

```
┌─────────────┐     POST /relay     ┌──────────────┐    Webhooks    ┌─────────────┐
│  Agents     │ ──────────────────→ │  Relay       │ ─────────────→ │  Discord    │
│  (Tony,     │                     │  Daemon      │                │  Server     │
│   Ultron,   │     GET /status     │  :8765       │                │             │
│   Jarvis)   │ ←────────────────── │              │                │  #tony      │
└─────────────┘                     │  Rate Limiter│                │  #ultron    │
                                    │  Queue (500) │                │  #jarvis    │
┌─────────────┐                     └──────────────┘                │  #hetzner   │
│  Telegram   │ ──→ Bridge ──→ ↑                                    │  #alerts    │
│  Messages   │    (format)                                         │  #dispatch  │
└─────────────┘                                                     │  #plc-live  │
                                                                    └─────────────┘
┌─────────────┐
│  Discord    │  /relay, /status, /config show, /fleet
│  Bot        │  Guild commands only
└─────────────┘
```

## Agent Roster

| Agent | Channel | Machine | Role |
|-------|---------|---------|------|
| Tony | #tony | Mac Mini (100.108.19.94) | Boss agent, coordinator |
| Ultron | #ultron | DO VPS (100.68.120.99) | Cloud reasoning, research |
| Jarvis | #jarvis | Travel Laptop (100.83.251.23) | PLC/Modbus edge |
| Hetzner | #hetzner | Hetzner (100.67.25.53) | Batch compute |

## Shared Channels

| Channel | Category | Purpose |
|---------|----------|---------|
| #plc-live | FACTORY FLOOR | Real-time PLC tag values |
| #alerts | FACTORY FLOOR | Incident notifications |
| #dispatch-log | AGENTS | Task delegation log |

## Acceptance Criteria

### Story 1 — Scaffold
- [ ] Directory tree matches spec
- [ ] `ruff check src/ tests/` clean
- [ ] `pytest tests/ -v` green (placeholder test)
- [ ] CI workflow runs on push/PR
- [ ] CLAUDE.md documents standards
- [ ] PRD.md documents requirements

### Story 2 — Config
- [ ] All 5 pydantic models validate correctly
- [ ] TOML loads and validates with field-level errors
- [ ] Token read from env var, never from file
- [ ] Default path `~/.factorylm/config.toml`
- [ ] Tests cover valid load, missing field, token from env

### Story 3 — Discord Setup
- [ ] Creates FACTORY FLOOR + AGENTS categories
- [ ] Creates all 7 channels
- [ ] Creates one webhook per channel
- [ ] Idempotent (skips existing)
- [ ] Writes valid config.toml (loadable by Story 2)
- [ ] Never writes bot token to file

### Story 4 — Relay Daemon
- [ ] POST /relay accepts {agent, message, format}, returns 202
- [ ] GET /status returns agent list, queue depths, uptime
- [ ] GET /health returns {ok: true}
- [ ] Unknown agent returns 404
- [ ] Graceful shutdown on SIGTERM drains queue
- [ ] Webhook posting extracted from AgentRelay pattern

### Story 5 — Rate Limiter
- [ ] Token bucket: 5 requests / 2 seconds per webhook
- [ ] Parses X-RateLimit-Remaining + X-RateLimit-Reset headers
- [ ] Queue maxsize=500 per webhook
- [ ] Drops oldest when full, logs WARNING
- [ ] drain_worker pulls from queue, retries on 429
- [ ] Integrated into relay daemon POST /relay

### Story 6 — Bridge
- [ ] `*bold*` → `**bold**` conversion
- [ ] `_italic_` → `*italic*` conversion
- [ ] HTML stripping
- [ ] Truncation on newline boundaries with suffix
- [ ] build_embed returns valid Discord embed payload
- [ ] build_alert_embed severity→color mapping (green/yellow/red)

### Story 7 — Slash Commands
- [ ] /relay <agent> <message> posts via relay, returns embed
- [ ] /status calls GET /status, returns embed
- [ ] /config show is ephemeral, hides webhook URLs and tokens
- [ ] /fleet shows fleet table
- [ ] on_ready logs guild info
- [ ] on_application_command_error returns ephemeral error
- [ ] All commands are guild-only

### Story 8 — README
- [ ] Architecture diagram
- [ ] Prerequisites and setup steps
- [ ] config.toml reference
- [ ] CLI command reference
- [ ] Security notes
- [ ] All acceptance criteria above are ticked
