# Conveyor Lab Style Guide

## TypeScript

- Keep API payloads validated with schemas before they reach service code.
- Prefer explicit domain unions for command names, run states, and outcomes.
- Keep hardware address constants in configuration files, not inline route handlers.
- Avoid broad `any` types except Express error boundaries.

## UI

- Use compact operational panels.
- Reserve red, amber, and green for state.
- Keep primary controls visible on mobile.
- Do not use decorative motion that resembles machine movement.

## Docs

- Update [API.md](API.md) when routes change.
- Update [MODBUS_MAP.md](MODBUS_MAP.md) when Factory I/O address mappings change.
- Update [TROUBLESHOOTING.md](TROUBLESHOOTING.md) when a recurring setup issue is found.
