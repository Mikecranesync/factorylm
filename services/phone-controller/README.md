# Phone Controller

Minimal HTTP API for dispatching Claude Code tasks from Mike's phone.

**Zero dependencies** — stdlib only, no pip install.

## Quick Start

```bash
export CONTROLLER_TOKEN=factorylm2026
python3 services/phone-controller/controller.py
```

## Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | No | System health (cpu, disk, uptime) |
| POST | `/run` | Yes | Dispatch a task |
| GET | `/status/<id>` | No | Check task status |
| GET | `/tasks` | No | List recent tasks |

## Run a Task

```bash
curl -X POST http://localhost:9876/run \
  -H "Authorization: Bearer factorylm2026" \
  -H "Content-Type: application/json" \
  -d '{"task": "list all Python files in services/"}'
```

Response:
```json
{"id": "a1b2c3d4", "status": "running", "message": "Task dispatched. Check GET /status/a1b2c3d4"}
```

## Options

| Env Var | Default | Description |
|---------|---------|-------------|
| `CONTROLLER_TOKEN` | (none) | Bearer token for auth. No token = open access |
| `CONTROLLER_PORT` | 9876 | Port to listen on |

POST body fields:
- `task` (required) — what to do
- `repo` (optional) — working directory, defaults to `~/factorylm`
- `claude` (optional) — if `false`, runs task as raw shell command instead of `claude --print`
