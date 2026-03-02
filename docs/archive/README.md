# Archived PLC Demo Implementations

These services were archived on 2026-03-02 as part of the V1 consolidation.
**`services/plc-modbus/`** was chosen as the V1 demo — the others are preserved
here for reference and future idea extraction.

## Why plc-modbus Won

- Self-contained backend + dashboard (FastAPI + SSE + live HTML)
- MockPLC class enables demo without hardware
- 12+ unit tests (most tested of all)
- Production-grade library in `src/factorylm_plc/`
- Real Modbus TCP code proven against the Micro 820
- Already has the API shape all adapters consume (`/api/plc/io`, `/api/devices`, `/api/stream`)

## What's Here

| Directory | Was | Best Ideas |
|-----------|-----|------------|
| `telegram-adapters/` | `services/telegram/` | Multi-node routing, HTTP PLC gateway, fault polling |
| `jarvis-telegram/` | `services/jarvis-telegram/` | Claude CLI bridge, Groq vision/voice, CMMS work orders |
| `discord-adapter/` | `services/discord-adapter/` | Rich embeds, scheduled reports, slash commands |
| `factorylm-discord-layer/` | `services/factorylm-discord-layer/` | Agent fleet relay, Telegram↔Discord bridging |
| `factorylm-cli/` | `packages/factorylm-cli/` | 3 PLC drivers (Modbus/EtherNet/IP/S7), Typer CLI, TagStore |

## Reusing Ideas

The best patterns from each service are documented in `docs/future/unified-io-adapter.md`
with attribution and implementation guidance.

## Running the V1 Demo

```bash
cd services/plc-modbus
pip install -e ".[backend]"
FACTORYLM_MOCK_MODE=true python -m factorylm_plc --port 8000
# Dashboard: http://localhost:8000
# API: http://localhost:8000/api/plc/io
```
