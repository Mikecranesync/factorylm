# Mission Control

Read-only dev monitoring dashboard for all FactoryLM systems.

## Run locally

```bash
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 3000
```

## Access from Tailnet

From any device on the Tailnet: `http://100.68.120.99:3000`

## Panels

- **Node Health** — VPS, Travel Laptop, PLC Laptop online/offline status
- **PLC Live Tags** — Motor, temperature, pressure, conveyor, faults
- **Antfarm Workflows** — Workflow list with agent/step counts
- **Jarvis Logs** — Last 30 OpenClaw journal lines

## Deploy to VPS

```bash
scp -r apps/mission-control/ root@100.68.120.99:/opt/openclaw/apps/mission-control/
scp scripts/mission-control.service root@100.68.120.99:/etc/systemd/system/
ssh root@100.68.120.99 "systemctl daemon-reload && systemctl enable --now mission-control"
```
