# Archived: FactoryLM CLI

**Originally at:** `packages/factorylm-cli/`
**Archived:** 2026-03-02

## What This Was

Full CLI toolkit for PLC communication, fault detection, and Discord relay. The most architecturally clean multi-protocol implementation in the repo.

### Supported PLCs

| Protocol | Driver | Install Extra |
|----------|--------|--------------|
| Modbus TCP | pymodbus | `factorylm[modbus]` |
| EtherNet/IP (Allen-Bradley) | pycomm3 | `factorylm[enip]` |
| S7 (Siemens) | python-snap7 | `factorylm[s7]` |

### Commands

| Command | Description |
|---------|-------------|
| `factorylm init` | Interactive setup wizard |
| `factorylm connect` | Test PLC connection |
| `factorylm tags` | Live tag viewer (Rich table, auto-refresh) |
| `factorylm up` | Start full pipeline: collector → DB → API → Discord → monitor |
| `factorylm serve` | Start web dashboard (FastAPI :8001) |
| `factorylm discord` | Start Discord bot only |
| `factorylm collect` | Start tag collector only (PLC → SQLite) |

## Best Ideas to Steal

1. **BasePLCClient ABC** — Clean abstract base with `connect()`, `read_tags()`, `write_tag()`, `disconnect()`
2. **EtherNet/IP driver** (plc/enip.py) — pycomm3-based Allen-Bradley driver
3. **S7 driver** (plc/s7.py) — snap7-based Siemens driver
4. **Factory pattern** — `create_client(protocol, host, port)` returns correct driver
5. **TagStore** — SQLite persistence with incidents table and Cosmos insight logging
6. **Typer CLI** — `factorylm tags` for live viewer, `factorylm connect` for interactive sessions
7. **Fault watcher** (monitor/watcher.py) — State transition detection with configurable thresholds
8. **TOML config** — `~/.factorylm/config.toml` with env var overrides

## Architecture

```
PLC (Modbus/EtherNet-IP/S7)
  |
  v
factorylm collect  -->  SQLite (~/.factorylm/tags.db)
  |                          |
  |                          v
  |                   factorylm serve (FastAPI :8001)
  |                          |
  v                          v
factorylm monitor    Web Dashboard (auto-refresh HMI)
  |
  v
NVIDIA Cosmos Reason 2  -->  Incident Analysis
  |
  v
factorylm discord  -->  Discord Slash Commands
```

## Key Files

- `plc/modbus.py` — Modbus TCP client
- `plc/enip.py` — EtherNet/IP client
- `plc/s7.py` — Siemens S7 client
- `config.py` — TOML config loader
- `discord/relay.py` — Webhook relay
- `monitor/watcher.py` — Fault detection
- `runner.py` — Main orchestrator/state machine
