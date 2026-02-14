# Cosmos Architecture — FactoryLM × NVIDIA Cosmos Reason 2

**Version:** 0.1 (Draft)  
**Author:** Mike Harper  
**Date:** 2026-02-13  
**Status:** PLANNING — Not yet implemented

---

## Data Flow

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        FACTORY FLOOR                                     │
│                                                                          │
│  ┌─────────────────┐          ┌─────────────────┐                        │
│  │  PLC / Micro820 │          │  Webcam (opt.)  │                        │
│  │  (or simulator) │          │  on cell         │                        │
│  └────────┬────────┘          └────────┬────────┘                        │
│           │ Modbus TCP                 │ RTSP / file                     │
│           ▼                            ▼                                 │
│  ┌─────────────────┐          ┌─────────────────┐                        │
│  │  Voltron Node   │          │  Video Store    │                        │
│  │  (tag reader)   │          │  (local disk /  │                        │
│  │                 │          │   object store) │                        │
│  └────────┬────────┘          └────────┬────────┘                        │
└───────────┼────────────────────────────┼─────────────────────────────────┘
            │ forwarder                  │ URL / path pointer
            ▼                            ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                          MATRIX (VPS)                                    │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                      PostgreSQL                                    │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │  │
│  │  │  tag_history  │  │   events     │  │  cosmos_insights         │  │  │
│  │  │  (ts, tag,    │  │  (ts, type,  │  │  (event_id, summary,    │  │  │
│  │  │   value)      │  │   node_id,   │  │   root_cause, confidence│  │  │
│  │  │              │  │   payload)   │  │   suggested_checks, …)  │  │  │
│  │  └──────────────┘  └──────┬───────┘  └──────────────────────────┘  │  │
│  └───────────────────────────┼────────────────────────────────────────┘  │
│                              │ new event                                 │
│                              ▼                                           │
│                    ┌─────────────────────┐                               │
│                    │  Cosmos Connector   │                               │
│                    │  (cosmos/agent.py)  │                               │
│                    │                     │                               │
│                    │  1. Receive event   │                               │
│                    │  2. Fetch N sec     │                               │
│                    │     of tag history  │                               │
│                    │  3. Get video URL   │                               │
│                    │  4. Call Cosmos     │                               │
│                    │     Reason 2 API    │                               │
│                    │  5. Store insight   │                               │
│                    └────────┬────────────┘                               │
│                             │                                            │
│              ┌──────────────┼──────────────┐                             │
│              ▼              ▼              ▼                              │
│  ┌───────────────┐ ┌───────────────┐ ┌───────────────┐                   │
│  │   Web HMI     │ │  Telegram /   │ │  Matrix API   │                   │
│  │  (incident    │ │  Chat Bot     │ │  (REST)       │                   │
│  │   detail)     │ │               │ │               │                   │
│  └───────────────┘ └───────────────┘ └───────────────┘                   │
└──────────────────────────────────────────────────────────────────────────┘
                             │
                             ▼
                  ┌─────────────────────┐
                  │  NVIDIA Cosmos      │
                  │  Reason 2 API       │
                  │  (cloud endpoint)   │
                  └─────────────────────┘
```

---

## Cosmos Connector Service (`cosmos/agent.py`)

### Responsibilities

1. **Subscribe to Matrix events** — listens for incident-type events (jam, anomaly, fault) from the events table or an internal message bus.
2. **Fetch tag context** — queries Postgres for N seconds (configurable, default 30s) of `tag_history` surrounding the event timestamp.
3. **Resolve video pointer** — looks up the video segment URL or file path covering the incident window from the video store.
4. **Call Cosmos Reason 2** — sends the incident bundle (tag snapshot + video reference) to the Cosmos Reason 2 API, following the pattern from the [NVIDIA Cosmos Cookbook](https://github.com/NVIDIA/Cosmos).
5. **Store CosmosInsight** — writes the structured result back to the `cosmos_insights` table in Postgres and publishes it to the Matrix event bus.

### Configuration

```yaml
cosmos:
  api_key_env: COSMOS_API_KEY
  model: cosmos-reason-2
  tag_window_seconds: 30
  video_window_seconds: 15
  max_retries: 3
  timeout_seconds: 60
```

### Event Types Handled

| Event Type | Trigger | Priority |
|------------|---------|----------|
| `jam` | Conveyor stall detected | High |
| `anomaly` | Tag value outside normal band | Medium |
| `fault` | PLC fault code raised | High |
| `drift` | Gradual sensor deviation | Low |

---

## CosmosInsight Dataclass

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class CosmosInsight:
    """Structured output from Cosmos Reason 2 for a single incident."""

    event_id: str
    timestamp: datetime
    summary: str                           # One-sentence description of what happened
    root_cause_hypothesis: str             # Cosmos's best guess at root cause
    confidence: float                      # 0.0 – 1.0
    suggested_checks: list[str]            # Ordered list of operator actions
    physical_observations: list[str]       # What Cosmos saw in the video
    tag_anomalies: list[str]               # Which tags were abnormal and how
    video_segment_url: Optional[str] = None
    model_version: str = "cosmos-reason-2"
    processing_time_ms: int = 0
    raw_response: dict = field(default_factory=dict)
```

---

## Postgres Schema: `cosmos_insights`

```sql
CREATE TABLE cosmos_insights (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id        UUID NOT NULL REFERENCES events(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    summary         TEXT NOT NULL,
    root_cause      TEXT NOT NULL,
    confidence      REAL NOT NULL CHECK (confidence >= 0.0 AND confidence <= 1.0),
    suggested_checks JSONB NOT NULL DEFAULT '[]',
    physical_obs    JSONB NOT NULL DEFAULT '[]',
    tag_anomalies   JSONB NOT NULL DEFAULT '[]',
    video_url       TEXT,
    model_version   TEXT NOT NULL DEFAULT 'cosmos-reason-2',
    processing_ms   INTEGER NOT NULL DEFAULT 0,
    raw_response    JSONB NOT NULL DEFAULT '{}'
);

CREATE INDEX idx_cosmos_insights_event ON cosmos_insights(event_id);
CREATE INDEX idx_cosmos_insights_created ON cosmos_insights(created_at DESC);
```

---

## Matrix / UX Integration

### Web HMI — Incident Detail View

When an operator clicks on an incident in the web HMI:

```
┌──────────────────────────────────────────────────────────────┐
│  INCIDENT: Conveyor Jam — Cell A — 2026-02-13 14:32:07      │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────────────────┐  ┌────────────────────────────┐ │
│  │  Tag History Chart      │  │  Video Thumbnail           │ │
│  │  ┄┄┄╱╲┄┄┄╱╲╲┄┄┄       │  │  ┌──────────────────────┐  │ │
│  │  motor_current          │  │  │  ▶ [00:14:30-00:15]  │  │ │
│  │  conveyor_speed         │  │  └──────────────────────┘  │ │
│  │  proximity_sensor       │  │                            │ │
│  └─────────────────────────┘  └────────────────────────────┘ │
│                                                              │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │  CosmosInsight                                  🟢 87%  │ │
│  │                                                          │ │
│  │  Summary: Motor current spiked 3.2× while conveyor      │ │
│  │  speed dropped to zero. Video shows carton wedged at     │ │
│  │  merge point.                                            │ │
│  │                                                          │ │
│  │  Root Cause: Carton misalignment at merge diverter       │ │
│  │  caused mechanical jam.                                  │ │
│  │                                                          │ │
│  │  Suggested Checks:                                       │ │
│  │    1. Clear jam at merge diverter                        │ │
│  │    2. Inspect diverter guide rail alignment              │ │
│  │    3. Check proximity sensor calibration                 │ │
│  └──────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

### Chat Client Endpoint

When an operator asks "What went wrong?" via Telegram or chat:

1. Matrix checks for a recent `CosmosInsight` matching the active or most recent incident.
2. If found, the insight summary and suggested checks are returned directly — no LLM call needed.
3. If no insight exists (Cosmos unavailable or event too old), the query falls through the normal intelligence stack (Layer 0 → Layer 3).
4. Follow-up questions ("Why do you think it's the diverter?") are answered using the `CosmosInsight.physical_observations` and `tag_anomalies` as grounding context.

---

## Safety Invariant

**Read-only constraint inherited from FactoryLM.** The Cosmos connector:

- ✓ Reads tag history from Postgres
- ✓ Reads video from the store
- ✓ Sends data to Cosmos Reason 2 for analysis
- ✓ Writes insights back to Postgres
- ✓ Suggests operator actions
- ✗ **Never** writes to PLCs
- ✗ **Never** starts, stops, or modifies equipment
- ✗ **Never** executes suggested actions automatically

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 0.1 | 2026-02-13 | Initial architecture draft |
