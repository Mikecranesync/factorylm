# Conveyor Lab Development

## Prerequisites

- Node.js 20
- npm
- Factory I/O with Modbus TCP/IP Server enabled, or simulator mode

## Run Locally

Backend:

```bash
cd apps/conveyor-lab/backend
npm ci
npm run dev
```

Frontend:

```bash
cd apps/conveyor-lab/frontend
npm ci
npm run dev
```

The backend defaults to port `8888`. The frontend defaults to port `3001` and proxies API and WebSocket traffic to `localhost:8888`.

## Useful Environment Variables

```bash
PORT=8888
MODBUS_HOST=100.83.251.23
MODBUS_PORT=502
MODBUS_UNIT_ID=1
FACTORYIO_AUTO_CONNECT=true
TELEGRAM_BOT_TOKEN=
NODE_ENV=development
```

Set `FACTORYIO_AUTO_CONNECT=false` to force simulator mode during UI and API development.

## Verification

```bash
cd apps/conveyor-lab/backend && npm run build
cd apps/conveyor-lab/frontend && npm run build
```

The GitHub Actions workflow in `.github/workflows/conveyor-lab.yml` runs both builds for Conveyor Lab changes.
