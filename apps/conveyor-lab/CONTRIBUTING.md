# Contributing to Conveyor Lab

Conveyor Lab is the FactoryLM bench app for Factory I/O conveyor testing. Keep changes scoped, testable, and safe for a lab simulator before connecting to real hardware.

## Local Setup

```bash
cd apps/conveyor-lab/backend
npm ci
npm run dev
```

```bash
cd apps/conveyor-lab/frontend
npm ci
npm run dev
```

Defaults:

- Backend: `http://localhost:8888`
- Frontend: `http://localhost:3001`
- WebSocket: `ws://localhost:8888/ws/telemetry`

## Development Rules

- Do not point Conveyor Lab at production PLCs.
- Prefer simulator mode unless Factory I/O is open and intentionally configured for the test.
- Keep Modbus address changes mirrored in [MODBUS_MAP.md](MODBUS_MAP.md).
- Keep API changes mirrored in [API.md](API.md).
- Do not commit secrets, `.env` files, Telegram tokens, Factory I/O credentials, or private network details.

## Pull Request Checklist

- Backend builds with `cd apps/conveyor-lab/backend && npm run build`.
- Frontend builds with `cd apps/conveyor-lab/frontend && npm run build`.
- New or changed env vars are documented in [README.md](README.md) and [../../docs/Config.md](../../docs/Config.md).
- New endpoints or WebSocket messages are documented in [API.md](API.md).
- Any hardware-facing behavior includes simulator-safe notes.
