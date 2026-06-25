# Conveyor Lab Troubleshooting

## Backend Starts on the Wrong Port

The backend defaults to `8888`. If another process is using that port:

```bash
PORT=8890 npm run dev
```

Update the frontend proxy before using a non-default backend port.

## Factory I/O Does Not Connect

Check:

- Factory I/O is running.
- The scene has the Modbus TCP/IP Server driver enabled.
- `MODBUS_HOST` points to the machine running Factory I/O.
- `MODBUS_PORT` is `502`.
- Local firewall rules allow inbound Modbus TCP.

To continue without Factory I/O:

```bash
FACTORYIO_AUTO_CONNECT=false npm run dev
```

## Commands Do Not Affect the Conveyor

Confirm the address map in [MODBUS_MAP.md](MODBUS_MAP.md) matches the loaded Factory I/O scene. The basic scene currently maps conveyor run and direction through coils and reads status through discrete inputs.

## Telegram Mini App Auth Fails

In development, the backend allows a dev fallback. In production, set `TELEGRAM_BOT_TOKEN` and verify that Telegram init data is present in the Mini App launch context.

## Frontend Cannot Reach API

Verify:

- Backend is running on `http://localhost:8888`.
- Frontend is running on `http://localhost:3001`.
- Browser console does not show WebSocket connection errors to `/ws/telemetry`.
