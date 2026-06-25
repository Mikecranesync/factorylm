# Conveyor Lab Roadmap

## Near Term

- Keep backend and frontend builds green in CI.
- Add targeted unit tests for command validation, run lifecycle, and simulator telemetry.
- Replace in-memory repositories with a small persistent store when run history needs to survive restarts.
- Expand API docs with exact response schemas.

## Lab Integration

- Confirm the Factory I/O scene address map and keep [MODBUS_MAP.md](MODBUS_MAP.md) current.
- Add clear UI indication for simulator vs Factory I/O mode.
- Add exportable run telemetry for analysis and demos.

## FactoryLM Integration

- Publish conveyor status into the broader FactoryLM operational model once the UNS boundary is defined.
- Add a read-only dashboard tile for Conveyor Lab health.
- Keep write-capable bench controls separate from production diagnostic surfaces.

## Security and Safety

- Harden production Telegram Mini App auth.
- Add operator confirmation for commands that affect hardware-facing outputs.
- Document deployment modes and keep simulator mode the default for development.
