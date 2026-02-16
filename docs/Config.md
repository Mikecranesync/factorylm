# FactoryLM — Configuration & Secrets Guide

**Last Updated:** 2026-02-12  
**Secret Manager:** [Doppler](https://www.doppler.com/) (free tier for personal use)

---

## How Secrets Work

1. **All secrets live in Doppler** — never in code, never in git.
2. **Each service reads env vars at startup** — Doppler injects them.
3. **Three environments:** `dev` (local laptop), `staging` (DO VPS), `prod` (future).
4. **One Doppler project per logical service** — keeps blast radius small.

---

## Doppler Project Layout

| Doppler Project | What It Covers | Environments |
|----------------|----------------|--------------|
| `factorylm-core` | LLM abstraction layer (`core/`) | dev, staging |
| `factorylm-plc` | PLC Modbus service (`services/plc-modbus/`) | dev, staging |
| `factorylm-copilot` | Telegram photo bot (`services/plc-copilot/`) | dev, staging |
| `factorylm-infra` | Shared infra keys (Axiom, Honeycomb, Doppler itself) | dev, staging |
| `openclaw` | OpenClaw bot instances (separate repo, same Doppler org) | dev (local), staging (VPS), legacy (Hostinger) |

---

## Environment Variable Naming Convention

All env vars follow this pattern: `SERVICE_PROVIDER_PURPOSE`

### AI / LLM Providers

| Env Var | Used By | Description | Doppler Project |
|---------|---------|-------------|-----------------|
| `GROQ_API_KEY` | core, openclaw | Groq cloud API key (free tier) | factorylm-core, openclaw |
| `CLAUDE_API_KEY` | core, openclaw | Anthropic API key | factorylm-core, openclaw |
| `DEEPSEEK_API_KEY` | core | DeepSeek API key | factorylm-core |
| `GEMINI_API_KEY` | plc-copilot, openclaw | Google Gemini API key | factorylm-copilot, openclaw |
| `OPENROUTER_API_KEY` | openclaw | OpenRouter API key | openclaw |

### Messaging / Bots

| Env Var | Used By | Description | Doppler Project |
|---------|---------|-------------|-----------------|
| `TELEGRAM_BOT_TOKEN` | plc-copilot | Telegram bot token | factorylm-copilot |
| `TELEGRAM_ALLOWED_USERS` | openclaw scripts | Comma-separated user IDs | factorylm-infra |

### External Services

| Env Var | Used By | Description | Doppler Project |
|---------|---------|-------------|-----------------|
| `CMMS_API_URL` | plc-copilot | Atlas CMMS API base URL | factorylm-copilot |
| `CMMS_USERNAME` | plc-copilot | CMMS login username | factorylm-copilot |
| `CMMS_PASSWORD` | plc-copilot | CMMS login password | factorylm-copilot |
| `CMMS_FRONTEND_URL` | plc-copilot | CMMS web UI URL | factorylm-copilot |
| `REGISTRATION_URL` | plc-copilot | User registration endpoint | factorylm-copilot |
| `BALENA_API_KEY` | Pi edge server | Balena Cloud API key | factorylm-infra |

### Observability

| Env Var | Used By | Description | Doppler Project |
|---------|---------|-------------|-----------------|
| `AXIOM_TOKEN` | Vector shippers | Axiom ingest token | factorylm-infra |
| `AXIOM_DATASET` | Vector shippers | Dataset name (default: `openclaw-logs`) | factorylm-infra |
| `HONEYCOMB_API_KEY` | OTel tracing | Honeycomb API key | factorylm-infra |
| `OTEL_SERVICE_NAME` | OTel tracing | Service name for traces | factorylm-infra |

### Infrastructure

| Env Var | Used By | Description | Doppler Project |
|---------|---------|-------------|-----------------|
| `VPS_HOST` | deploy scripts | DigitalOcean VPS IP/hostname | factorylm-infra |
| `VPS_LEGACY_HOST` | deploy scripts | Hostinger VPS IP (until decommissioned) | factorylm-infra |
| `PLC_HOST` | plc-modbus | PLC IP address (default: 192.168.1.100) | factorylm-plc |
| `PLC_PORT` | plc-modbus | Modbus TCP port (default: 502) | factorylm-plc |

### Accounts (Non-Secret but Tracked)

| Env Var | Used By | Description | Doppler Project |
|---------|---------|-------------|-----------------|
| `WIFI_SSID` | Pi setup | WiFi network name | factorylm-infra |
| `WIFI_PASSWORD` | Pi setup | WiFi password | factorylm-infra |

---

## Per-Service Config Reference

### `core/` — LLM Abstraction Layer

```bash
# Required
GROQ_API_KEY=        # Get from https://console.groq.com/keys

# Optional (if using these providers)
CLAUDE_API_KEY=      # Get from https://console.anthropic.com
DEEPSEEK_API_KEY=    # Get from https://platform.deepseek.com

# Config (have defaults in config.py)
LLM_PROVIDER=groq           # groq | claude | deepseek | flm
LLM_MODEL=                  # Override default model per provider
LLM_API_KEY=                # Generic key (provider-specific vars take precedence)
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=4096
```

**Test command:** `cd core && pytest`

### `services/plc-modbus/` — PLC Modbus Client

```bash
# Required for real hardware
PLC_HOST=192.168.1.100
PLC_PORT=502

# Optional
PLC_USE_MOCK=true    # Use mock PLC instead of real hardware
PLC_TIMEOUT=3        # Connection timeout in seconds
```

**Test command:** `cd services/plc-modbus && pytest`

### `services/plc-copilot/` — Telegram Photo Bot

```bash
# Required
TELEGRAM_BOT_TOKEN=          # From @BotFather
GEMINI_API_KEY=              # From https://console.cloud.google.com
CMMS_API_URL=                # Atlas CMMS API endpoint
CMMS_USERNAME=               # CMMS login
CMMS_PASSWORD=               # CMMS password

# Optional
CMMS_FRONTEND_URL=http://72.60.175.144  # Web UI for work order links
REGISTRATION_URL=                        # User registration endpoint
```

**Test command:** None yet (single-file bot, no tests)

### `scripts/honeycomb/` — OpenTelemetry Tracing

```bash
# Required
HONEYCOMB_API_KEY=    # From https://ui.honeycomb.io/account
OTEL_SERVICE_NAME=    # e.g., openclaw-jarvis-local

# Auto-set by setup scripts
OTEL_EXPORTER_OTLP_ENDPOINT=https://api.honeycomb.io
OTEL_EXPORTER_OTLP_HEADERS=x-honeycomb-team=$HONEYCOMB_API_KEY
```

### Axiom Log Shippers

```bash
# Required
AXIOM_TOKEN=          # From https://app.axiom.co → Settings → API Tokens
AXIOM_DATASET=openclaw-logs
```

---

## Setting Up Doppler

### First Time (One-Time Setup)

```bash
# 1. Install Doppler CLI
# Windows (PowerShell):
winget install doppler

# Linux:
curl -sLf https://cli.doppler.com/install.sh | sh

# 2. Authenticate
doppler login

# 3. Create projects (run once)
doppler projects create factorylm-core
doppler projects create factorylm-plc
doppler projects create factorylm-copilot
doppler projects create factorylm-infra
doppler projects create openclaw
```

### Adding a Secret

```bash
# Set a secret in a specific project/environment
doppler secrets set GROQ_API_KEY "gsk_your_key_here" \
  --project factorylm-core --config dev

# Set the same key for staging (VPS)
doppler secrets set GROQ_API_KEY "gsk_your_key_here" \
  --project factorylm-core --config stg
```

### Running a Service with Doppler

```bash
# Instead of manually exporting env vars:
doppler run --project factorylm-plc --config dev -- pytest

# Or for a long-running service:
doppler run --project factorylm-copilot --config dev -- python photo_to_cmms_bot.py
```

### On a VPS (Systemd Integration)

```bash
# Install Doppler CLI on VPS
ssh vps "curl -sLf https://cli.doppler.com/install.sh | sh"

# Set up service token (no interactive login needed)
ssh vps "doppler configure set token dp.st.xxx --scope /root/.openclaw"

# Update systemd service to use Doppler
# In /etc/systemd/system/openclaw.service:
# ExecStart=doppler run --project openclaw --config stg -- node gateway.js
```

---

## Migration Checklist

When moving a service to Doppler:

- [ ] Identify all env vars the service needs (check this doc)
- [ ] Add them to the appropriate Doppler project/environment
- [ ] Replace any hardcoded values with `os.getenv("VAR_NAME")` or `process.env.VAR_NAME`
- [ ] Test with `doppler run -- <command>`
- [ ] Update systemd/startup scripts if on a VPS
- [ ] Remove any `.env` files that are no longer needed
- [ ] Update this doc if new env vars were added

---

*This document is the single source of truth for configuration. Keep it updated.*
