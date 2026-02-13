# Local Development Setup — FactoryLM

## Prerequisites

- **OS:** Windows 11 (primary), Linux/macOS also supported
- **Python:** 3.11+ (check with `python --version`)
- **Node.js:** 22+ (for OpenClaw/clawdbot, optional)
- **Docker:** Optional but recommended for Postgres
- **Git:** 2.x+
- **Ollama:** Optional, for local LLM (Layer 1/2)

## Step 1: Clone the repo

```bash
git clone https://github.com/Mikecranesync/factorylm.git
cd factorylm
```

## Step 2: Python environment

```bash
# Create a virtual environment (recommended)
python -m venv .venv

# Activate (Windows PowerShell)
.\.venv\Scripts\Activate.ps1

# Activate (Linux/macOS)
source .venv/bin/activate

# Install core dependencies
pip install -e core/
pip install -e "core/[otel]"  # Optional: OpenTelemetry tracing
```

## Step 3: Start Postgres (for Matrix API)

```bash
# Option A: Docker (recommended)
docker run -d --name factorylm-postgres \
  -e POSTGRES_USER=factorylm \
  -e POSTGRES_PASSWORD=localdev \
  -e POSTGRES_DB=matrix \
  -p 5432:5432 \
  postgres:16

# Option B: Use Neon (serverless, free tier)
# Set DATABASE_URL env var to your Neon connection string

# Option C: Skip if you're only working on core/, plc-modbus, or cosmos
```

## Step 4: Run services

| Service | Command | Port | Notes |
|---------|---------|------|-------|
| PLC Modbus API | `cd services/plc-modbus && uvicorn backend.main:app --reload` | 8000 | Use `PLC_USE_MOCK=true` for simulator |
| My-Ralph API | `cd my-ralph && python -m uvicorn api.main:app --reload` | 8000 | Change port if running alongside PLC API |
| PLC Copilot bot | `cd services/plc-copilot && python photo_to_cmms_bot.py` | — | Needs `TELEGRAM_BOT_TOKEN` env var |

## Step 5: Run tests

```bash
# Core (148 tests)
cd core && pytest

# PLC Modbus (162 tests)
cd services/plc-modbus && pytest

# My-Ralph (321 BATS + 34 pytest)
cd my-ralph && npm test

# Cosmos agent (5 tests)
pytest tests/unit/test_cosmos_agent.py
```

## Step 6: PLC Simulator (no real hardware needed)

```bash
# Start PLC Modbus API with mock PLC
cd services/plc-modbus
PLC_USE_MOCK=true uvicorn backend.main:app --reload --port 8000

# The mock PLC simulates a Micro 820 with:
# - Coils (digital outputs)
# - Holding registers (analog values)
# - Input registers (sensor readings)
```

## Step 7: Secrets via Doppler (optional)

```bash
# If you have Doppler set up:
doppler run --project factorylm-core --config dev -- pytest

# Otherwise, set env vars directly:
# Windows PowerShell:
$env:GROQ_API_KEY = "your-key"
$env:TELEGRAM_BOT_TOKEN = "your-token"

# Linux/macOS:
export GROQ_API_KEY="your-key"
export TELEGRAM_BOT_TOKEN="your-token"
```

## Step 8: Ollama (local LLM, optional)

```bash
# Install Ollama: https://ollama.ai
# Pull a small model:
ollama pull qwen2.5:0.5b

# FactoryLM core can use it:
LLM_PROVIDER=flm LLM_API_KEY=unused python -c "from factorylm.config import get_config; print(get_config())"
```

## Deployment profiles

| Profile | Where | What runs | Config |
|---------|-------|-----------|--------|
| `local-dev` | Laptop | Everything (mock PLC, local Postgres, local LLM) | `.env` or Doppler dev |
| `demo-vps` | Hetzner | Caddy reverse proxy only — forwards to local | `/etc/caddy/Caddyfile` |
