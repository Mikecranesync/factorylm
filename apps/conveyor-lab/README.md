# Conveyor Lab

A Telegram Mini App for simulating and monitoring industrial conveyor VFD (Variable Frequency Drive) systems.

## Overview

Conveyor Lab provides:
- Real-time VFD status monitoring
- Speed and direction control
- Run management with telemetry recording
- AI-powered analysis integration (Cosmos models)
- Feedback collection for RLHF training

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    Telegram Mini App                          │
│  ┌────────────────────────────────────────────────────────┐  │
│  │                   React Frontend                        │  │
│  │  • Status Page (VFD control + live telemetry)          │  │
│  │  • New Run Page (configure and start runs)             │  │
│  │  • Runs List Page (history with filtering)             │  │
│  │  • Run Detail Page (telemetry, analysis, feedback)     │  │
│  └────────────────────────────────────────────────────────┘  │
│                           │                                   │
│                    HTTP + WebSocket                           │
│                           │                                   │
│  ┌────────────────────────────────────────────────────────┐  │
│  │                  Express Backend                        │  │
│  │  • /api/status - VFD status                            │  │
│  │  • /api/command - Control commands                     │  │
│  │  • /api/runs - Run CRUD                                │  │
│  │  • /ws/telemetry - Real-time streaming                 │  │
│  └────────────────────────────────────────────────────────┘  │
│                           │                                   │
│                      SQLite DB                                │
└──────────────────────────────────────────────────────────────┘
```

## Quick Start

### Backend

```bash
cd backend
npm install
npm run dev
```

Server starts at http://localhost:3001

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Dev server starts at http://localhost:5173

## API Reference

### Status Endpoints

**GET /api/status**
Returns current VFD status.

```json
{
  "runState": "running",
  "direction": "forward",
  "commandHz": 30.0,
  "actualHz": 29.5,
  "motorCurrent": 2.5,
  "faultCode": 0,
  "faultText": "",
  "timestamp": 1708200000000
}
```

**POST /api/command**
Send control commands.

```json
{
  "action": "start" | "stop" | "set_speed" | "set_direction" | "clear_fault",
  "value": 30 | "forward" | "reverse",
  "runId": "optional-run-id"
}
```

### Run Endpoints

**POST /api/runs**
Create a new run.

```json
{
  "name": "Morning calibration",
  "description": "Testing new belt",
  "direction": "forward",
  "targetSpeedHz": 30,
  "maxDurationSeconds": 300,
  "tags": ["calibration", "test"]
}
```

**GET /api/runs**
List runs with pagination and filtering.

Query params: `limit`, `offset`, `tags`, `dateFrom`, `dateTo`

**GET /api/runs/:id**
Get run details with telemetry, analysis, and feedback.

**POST /api/runs/:id/stop**
Stop a running run.

**POST /api/runs/:id/feedback**
Add feedback for RLHF training.

```json
{
  "modelAnalysisId": "analysis-id",
  "actionTaken": "followed" | "partial" | "ignored",
  "rating": 1-5,
  "tags": ["helpful", "accurate"],
  "notes": "Optional notes"
}
```

**POST /api/runs/:id/model-analysis**
Add AI analysis to a run.

```json
{
  "cosmosModel": "cosmos-reason2-2b",
  "summary": "Analysis summary",
  "suggestedActions": ["Action 1", "Action 2"],
  "confidence": 0.85,
  "reasoning": "Optional reasoning"
}
```

### WebSocket

**ws://host/ws/telemetry**

Connect with optional auth: `?initData=<telegram-init-data>`

Message types:
- `status` - VFD status updates
- `telemetry` - Telemetry data points
- `runComplete` - Run completion notification
- `error` - Error messages

## Telegram Integration

The app uses the Telegram Mini Apps SDK for:
- User authentication via `initData` validation
- Haptic feedback on interactions
- Main/Back button integration
- Theme color adaptation

### Testing Outside Telegram

The app works in a regular browser for development. Authentication is bypassed when `initData` is not present.

## Database Schema

- **users** - Telegram user records
- **runs** - Run configurations and summaries
- **telemetry_points** - Time-series VFD data
- **model_analyses** - AI analysis results
- **feedback** - User feedback for RLHF
- **media** - Associated videos/images

## Configuration

Environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| PORT | 3001 | Backend server port |
| TELEGRAM_BOT_TOKEN | - | Bot token for auth validation |
| DATABASE_URL | ./conveyor-lab.db | SQLite database path |

## Cosmos Integration

The app is designed to collect training data for Cosmos Reason2 fine-tuning:

1. **Telemetry Collection** - VFD data points during runs
2. **Model Analysis** - AI predictions stored with runs
3. **Feedback Loop** - Operator feedback on AI recommendations

Export data for training:
```bash
sqlite3 conveyor-lab.db ".mode json" "SELECT * FROM runs JOIN feedback ON runs.id = feedback.runId" > training_data.json
```

## Development

### Tech Stack

**Backend:**
- Node.js + TypeScript
- Express
- better-sqlite3
- ws (WebSocket)
- Zod validation

**Frontend:**
- React + TypeScript
- Vite
- TailwindCSS
- React Query
- Zustand
- Recharts

### Project Structure

```
conveyor-lab/
├── backend/
│   └── src/
│       ├── index.ts           # Entry point
│       ├── types/             # TypeScript types
│       ├── models/            # Database & repositories
│       ├── services/          # VFD simulator, WebSocket
│       ├── middleware/        # Telegram auth
│       └── routes/            # API routes
└── frontend/
    └── src/
        ├── main.tsx           # Entry point
        ├── App.tsx            # Router
        ├── types/             # Shared types
        ├── store/             # Zustand store
        ├── hooks/             # Custom hooks
        ├── services/          # API client
        ├── components/        # UI components
        └── pages/             # Page components
```
