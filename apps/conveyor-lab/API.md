# Conveyor Lab API

Base URL: `http://localhost:8888`

## Health

### `GET /api/health`

Returns backend health and WebSocket client count.

```json
{
  "status": "ok",
  "service": "conveyor-lab-backend",
  "timestamp": 1710000000000,
  "wsClients": 1
}
```

## Status and Commands

### `GET /api/status`

Returns current conveyor status and connection mode.

### `POST /api/command`

Sends a VFD-style command.

```json
{
  "action": "set_speed",
  "value": 30,
  "runId": "run_123"
}
```

Supported actions:

- `start`
- `stop`
- `set_speed`
- `set_direction`
- `clear_fault`
- `inject_fault`

`set_direction` expects `value` to be `forward` or `reverse`. `set_speed` expects a number. `inject_fault` is for development and test use only.

## Runs

### `POST /api/runs`

Creates and starts a run.

```json
{
  "name": "Demo run",
  "description": "Factory I/O conveyor test",
  "direction": "forward",
  "targetSpeedHz": 30,
  "maxDurationSeconds": 300,
  "tags": ["factoryio", "bench"]
}
```

### `GET /api/runs`

Lists runs. Optional query parameters:

- `limit`
- `offset`
- `tags`
- `dateFrom`
- `dateTo`

### `GET /api/runs/:id`

Returns run detail with telemetry, model analysis, feedback, and media.

### `POST /api/runs/:id/stop`

Stops an active run.

### `POST /api/runs/:id/feedback`

Adds operator feedback to a run.

```json
{
  "modelAnalysisId": "analysis_123",
  "actionTaken": "followed",
  "rating": 5,
  "tags": ["confirmed"],
  "notes": "Recommendation matched observed behavior."
}
```

### `POST /api/runs/:id/model-analysis`

Stores a precomputed model analysis result.

```json
{
  "cosmosModel": "nvidia/cosmos-reason2-2b",
  "summary": "Conveyor started and reached expected speed.",
  "suggestedActions": ["Continue monitoring exit sensor timing."],
  "confidence": 0.82,
  "reasoning": "Telemetry stayed inside expected range."
}
```

## WebSocket

### `/ws/telemetry`

Streams conveyor telemetry and run completion events.

Common message types:

- `status`
- `telemetry`
- `runComplete`
- `error`
