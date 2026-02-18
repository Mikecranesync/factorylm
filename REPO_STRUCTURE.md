# FactoryLM Repository Structure

> **This is THE monolith. All code lives here.**
> Last consolidated: 2026-02-05

## Directory Map

```
factorylm/
├── analytics/          # Time-series analysis
│   ├── baseline_builder.py    # Learn normal patterns
│   ├── drift_detector.py      # Detect anomalies
│   └── pattern_embedder.py    # Embedding for similarity
│
├── apps/               # Frontend applications
│   ├── dashboard/      # Main dashboard
│   ├── web/           # Marketing site components
│   ├── cmms/          # CMMS integration
│   └── portal/        # Customer portal
│
├── brain/              # AI/LLM intelligence layer
│   ├── hammurabi.py   # Quality judge (pass/fail gate)
│   ├── herodotus.py   # Knowledge recorder
│   ├── schemas/       # Database schemas
│   └── templates/     # Prompt templates
│
├── collectors/         # PLC data collection
│   ├── ab_collector_tasks.py     # Allen-Bradley
│   ├── s7_collector_tasks.py     # Siemens S7
│   └── modbus_collector_tasks.py # Modbus TCP/RTU
│
├── core/               # Core library
│   ├── src/factorylm/ # Main package
│   ├── adapters/      # External integrations
│   └── services/      # Business logic
│
├── docs/               # Documentation
│   ├── SPEC-DRIVEN-DEVELOPMENT.md
│   ├── PHARAOHS-OBSERVATORY.md
│   └── ARCHIMEDES-LOGIC-MAP.md
│
├── execution/          # Action execution
│   └── action_executor.py  # Execute commands on PLCs
│
├── gateway/            # Edge gateway (Pi)
│   └── src/           # Gateway service code
│
├── monitoring/         # System health
│   └── system_health.py
│
├── packages/           # Shared packages
│   ├── auth/          # Authentication
│   ├── db/            # Database utilities
│   ├── ui/            # UI components
│   └── config/        # Configuration
│
├── plc-client/         # PLC communication library
│   └── src/           # Modbus/CIP client code
│
├── plc-client-factoryio/  # Factory I/O integration
│
├── scripts/            # Utility scripts
│   ├── pi-setup/      # Raspberry Pi setup
│   └── ralph/         # Ralph deployment
│
├── services/           # Microservices
│   ├── plc-copilot/   # Telegram bot
│   └── plc-modbus/    # Modbus service
│
├── specs/              # Pydantic quality specs
│   └── demo_content_spec.py  # YC demo quality gate
│
├── workers/            # Celery task workers
│   ├── celery_app.py          # Celery configuration
│   ├── base_worker.py         # Base worker class
│   ├── conductor_tasks.py     # Orchestration
│   ├── demo_director_tasks.py # YC demo automation
│   ├── obs_controller_tasks.py # OBS camera control
│   ├── plc_sync_tasks.py      # PLC I/O sync
│   ├── polish_tasks.py        # Quality polish loop
│   ├── quality_gate.py        # Quality decorator
│   └── ... (20+ more workers)
│
└── tests/              # Test suite
```

## Key Files

| File | Purpose |
|------|---------|
| `workers/celery_app.py` | Celery app configuration |
| `workers/quality_gate.py` | `@quality_gated` decorator |
| `brain/hammurabi.py` | LLM-as-judge for quality |
| `specs/demo_content_spec.py` | Pydantic specs for demo |
| `CLAUDE.md` | AI agent instructions |
| `README.md` | Project overview |

## Running the Workers

```bash
cd /opt/factorylm
source venv/bin/activate  # if using venv

# Start Celery worker
celery -A workers.celery_app worker --loglevel=info

# Start Celery beat (scheduler)
celery -A workers.celery_app beat --loglevel=info

# Run specific task
celery -A workers.celery_app call demo.status
```

## Tags

- `v0.1.0-consolidated` - First consolidated monolith
- `yc-demo-prep` - YC demo preparation starting point

## Deprecated Repos (Archive These)

These repos are now merged into factorylm:
- `factorylm-core` → merged into `core/`
- `factorylm-plc-client` → merged into `plc-client/`
- `factorylm-mini` → merged into `gateway/`
- `mikes-brain` → merged into `brain/`
- `pi-gateway` → merged into `gateway/`

Keep separate:
- `factorylm-landing` - Marketing website (different deploy)
- `jarvis-workspace` - Clawdbot config (not FactoryLM code)
