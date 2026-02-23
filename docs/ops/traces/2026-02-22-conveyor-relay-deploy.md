# Ops Trace: Conveyor Relay Deploy

**Date**: 2026-02-22
**Service**: conveyor-relay
**VPS**: 100.68.120.99
**Port**: 8400

## What changed

Deployed new `conveyor-relay` FastAPI service to `/opt/conveyor-relay/` on the VPS.

- `relay.py` — proxies commands to conveyor-lab backend on PLC laptop (:3001)
- `static/index.html` — embeddable control page with live webcam + buttons
- `requirements.txt` — fastapi, uvicorn, httpx, opencv-python

## Systemd

```
/etc/systemd/system/conveyor-relay.service
ExecStart=/usr/bin/python3 relay.py
Environment=CONVEYOR_BACKEND_URL=http://100.72.2.99:3001
Environment=WEBCAM_URL=http://100.72.2.99:8081/stream
Environment=PORT=8400
```

## Verification

```
curl http://localhost:8400/api/health
→ {"status":"ok","service":"conveyor-relay","commandCount":0}
```

## Tags

- `conveyor-relay/dev/v1.0.0`
- `conveyor-relay/staging/v1.0.0`
- `conveyor-relay/prod/v1.0.0`
