# Infrastructure Scripts & Tools Overview

## Script inventory

| Script | Location | Purpose | When to use |
|--------|----------|---------|-------------|
| `scripts/honeycomb/tracing.js` | `scripts/honeycomb/` | OTel bootstrap for Node.js services | Loaded via `NODE_OPTIONS=-r tracing.js` |
| `scripts/honeycomb/setup-vps.sh` | `scripts/honeycomb/` | Install OTel deps + configure systemd on Linux VPS | First-time VPS tracing setup |
| `scripts/honeycomb/setup-local.ps1` | `scripts/honeycomb/` | Install OTel deps + set env vars on Windows | First-time local tracing setup |
| `scripts/honeycomb/install-deps.sh` | `scripts/honeycomb/` | Install OTel npm packages globally (Linux) | Dependency install |
| `scripts/honeycomb/install-deps.ps1` | `scripts/honeycomb/` | Install OTel npm packages globally (Windows) | Dependency install |
| `scripts/fix_ultron_config.py` | `scripts/` | Fix VPS model configuration | One-time fix (applied) |
| `scripts/install-openclaw-service.ps1` | `scripts/` | Install OpenClaw as Windows service | Local OpenClaw setup |
| `scripts/openclaw-watchdog.ps1` | `scripts/` | Monitor and restart OpenClaw if it crashes | Run as scheduled task |

## Infra directories

| Directory | Purpose |
|-----------|---------|
| `infra/migration/` | VPS migration docs, runbooks, progress tracking |
| `infra/local/` | (Planned) Docker Compose for local dev stack |
| `scripts/honeycomb/` | OpenTelemetry / Honeycomb setup scripts |
| `scripts/` | Misc utility scripts (VPS fixes, service installers) |

## External infrastructure

| Service | Purpose | Management |
|---------|---------|------------|
| Doppler | Secret management | `doppler` CLI or web UI |
| Tailscale | Mesh VPN between laptop ↔ VPSes | `tailscale` CLI |
| Honeycomb | Distributed tracing | Web UI at ui.honeycomb.io |
| Axiom | Log aggregation | Web UI at app.axiom.co |
| GitHub Actions | CI for My-Ralph | `.github/workflows/` |

## Key config files

| File | What it configures |
|------|-------------------|
| `config/cosmos.yaml` | Cosmos Reason 2 connector settings |
| `core/src/factorylm/config.py` | LLM provider defaults, model selection |
| `services/plc-modbus/.env.example` | PLC connection settings template |
| `services/plc-copilot/.env.example` | Telegram bot + CMMS settings template |
| `turbo.json` | Turborepo pipeline (mostly unused) |
| `package.json` | Monorepo workspace definitions |
