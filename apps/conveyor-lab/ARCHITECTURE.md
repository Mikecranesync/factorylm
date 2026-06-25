# Conveyor Lab Architecture

Conveyor Lab is a bench control and telemetry app for the Factory I/O conveyor scene. It is separate from FactoryLM's read-only production diagnostic posture and should not be aimed at production equipment.

## Runtime Shape

```text
Browser / Telegram Mini App
  -> Vite frontend
  -> Express backend REST API
  -> WebSocket telemetry stream
  -> Conveyor service
  -> Factory I/O Modbus TCP adapter or simulator
```

## Components

| Component | Path | Responsibility |
|-----------|------|----------------|
| Frontend | `frontend/src/` | HMI panels, run controls, telemetry views, Telegram Mini App shell |
| Backend API | `backend/src/index.ts` | Express app, health route, API route mounting, WebSocket server |
| Status routes | `backend/src/routes/status.ts` | VFD status and control commands |
| Run routes | `backend/src/routes/runs.ts` | Run creation, history, feedback, model-analysis records |
| Conveyor service | `backend/src/services/conveyor.ts` | Chooses Factory I/O adapter or simulator mode |
| Factory I/O adapter | `backend/src/services/modbus-conveyor-adapter.ts` | Modbus TCP reads, writes, telemetry summaries |
| Simulator | `backend/src/services/conveyor-simulator.ts` | Local conveyor behavior for dev and fallback |
| In-memory store | `backend/src/models/` | Run, telemetry, feedback, media, and analysis repositories |

## Data Flow

1. The frontend calls `/api/status`, `/api/command`, and `/api/runs`.
2. The backend chooses Factory I/O mode when Modbus auto-connect succeeds; otherwise it falls back to simulator mode.
3. Telemetry is published over `/ws/telemetry`.
4. Run summaries are attached when a run completes, stops, or faults.

## Safety Boundary

Conveyor Lab writes commands to a lab simulator or bench scene. It is not a production PLC control service. Any move toward real equipment needs explicit interlocks, authentication, operator confirmation, and a separate safety review.
