# PEPPER - FactoryLM Telegram Bot System

**Dual-Mode AI Assistant with Digital Twins**

PEPPER is a production-grade Telegram bot that provides two access modes:
- **God Mode (Pepper Prime)** - Full system access for Mike
- **Demo Mode (Pepper)** - Guardrailed access for customers/technicians

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        PEPPER SYSTEM                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  @PepperPrimeBot              @FactoryLMBot                     │
│  (God Mode)                   (Demo Mode)                       │
│       │                            │                            │
│       └────────────┬───────────────┘                            │
│                    │                                            │
│            ┌───────┴───────┐                                    │
│            │   GATEWAY     │                                    │
│            │  Mode Router  │                                    │
│            └───────┬───────┘                                    │
│                    │                                            │
│     ┌──────────────┼──────────────┐                            │
│     │              │              │                             │
│  ┌──┴──┐       ┌──┴──┐       ┌──┴──┐                          │
│  │ PLC │       │TRVL │       │ VPS │   ← Digital Twins         │
│  │Twin │       │Twin │       │Twin │                           │
│  └─────┘       └─────┘       └─────┘                           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Quick Start

### Installation

```bash
# Clone repository
git clone https://github.com/Mikecranesync/factorylm.git
cd factorylm/services/telegram/pepper

# Run installer (on VPS)
sudo ./scripts/install.sh

# Configure environment
nano /root/pepper/.env

# Start services
systemctl enable --now pepper pepper-watchdog
```

### CLI Commands

```bash
# Deployment
pepper deploy                    # Deploy with patch bump
pepper deploy --bump minor       # Minor version bump
pepper deploy --dry-run          # Preview deployment

# Rollback
pepper rollback                  # Rollback to previous (<30s)
pepper rollback v1.1.2           # Rollback to specific version
pepper rollback --list           # List available versions

# Monitoring
pepper status                    # Current status
pepper health                    # Run health checks
pepper logs -f                   # Follow logs
```

## Directory Structure

```
pepper/
├── __init__.py              # Package init
├── gateway.py               # Main Telegram bot entry
├── modes.py                 # God/Demo mode handling
├── config.py                # Configuration loading
├── config.yaml              # Main configuration
├── watchdog.yaml            # Watchdog configuration
├── requirements.txt         # Python dependencies
│
├── twins/                   # Digital Twin system
│   ├── twin.py              # Base DigitalTwin class
│   ├── registry.py          # Twin registry
│   ├── plc_twin.py          # PLC Laptop twin
│   ├── travel_twin.py       # Travel Laptop twin
│   └── vps_twin.py          # VPS twin
│
├── tools/                   # Tool implementations
│   ├── base.py              # BaseTool abstract class
│   ├── guardrails.py        # Demo mode access control
│   ├── filesystem.py        # File operations (God)
│   ├── shell.py             # Shell commands (God)
│   ├── equipment.py         # Equipment status (Both)
│   ├── diagnosis.py         # AI diagnosis (Both)
│   ├── work_orders.py       # Work orders (Demo)
│   └── escalation.py        # Escalation (Demo)
│
├── personas/                # Personality system
│   ├── loader.py            # Persona loading
│   ├── formatter.py         # Response formatting
│   ├── SOUL_GOD.md          # God mode persona
│   └── SOUL_DEMO.md         # Demo mode persona
│
├── intelligence/            # AI routing
│   ├── router.py            # Layer routing
│   ├── layer0_kb.py         # Knowledge base
│   ├── layer2_local.py      # Groq LLM
│   └── layer3_cloud.py      # Claude fallback
│
├── watchdog/                # Monitoring system
│   ├── health.py            # Health checks
│   ├── drift.py             # Config drift detection
│   ├── api_validator.py     # API key validation
│   ├── fingerprint.py       # System fingerprinting
│   ├── recovery.py          # Auto-recovery
│   ├── alerts.py            # Alert routing
│   └── main.py              # Watchdog orchestrator
│
├── deploy/                  # Versioning & deployment
│   ├── versioning.py        # Version management
│   ├── deployer.py          # Deployment logic
│   ├── state.py             # State snapshots
│   ├── rollback.py          # Rollback functionality
│   └── cli.py               # CLI commands
│
└── scripts/                 # Installation & services
    ├── install.sh           # Installation script
    ├── pepper.service       # Systemd service
    ├── pepper-watchdog.service
    └── pepper-cli           # CLI wrapper
```

## Configuration

### config.yaml

```yaml
version: "1.0.0"

bots:
  prime:
    name: "Pepper Prime"
    token: ${PEPPER_PRIME_TOKEN}
  demo:
    name: "Pepper"
    token: ${FACTORYLM_BOT_TOKEN}

god_users:
  - 8445149012  # Mike's Telegram ID

nodes:
  plc:
    url: "http://100.72.2.99:8765"
    matrix_api: "http://100.72.2.99:8000"
  travel:
    url: "http://100.83.251.23:8765"
  vps:
    url: "http://localhost:18789"
```

### Environment Variables

```bash
# Bot Tokens
PEPPER_PRIME_TOKEN=      # God Mode bot
FACTORYLM_BOT_TOKEN=     # Demo Mode bot

# API Keys
GROQ_API_KEY=            # Primary LLM
ANTHROPIC_API_KEY=       # Fallback LLM
```

## Digital Twins

Each physical device has a digital twin that knows:
- **Capabilities** - What the device can do
- **Status** - Online/Offline/Degraded
- **API** - How to communicate with it

### PLC Twin (100.72.2.99)
- Factory I/O simulation
- Micro 820 PLC connection
- Matrix API for tag database
- Fault injection capability

### Travel Twin (100.83.251.23)
- Claude Code access
- Git operations
- Development tools
- Deployment capability

### VPS Twin (localhost)
- Telegram gateway
- n8n workflows
- Shell access
- Clawdbot integration

## Modes

### God Mode (Pepper Prime)

Full access for Mike:
- Filesystem read/write
- Shell command execution
- Database operations
- PLC read/write
- Git operations
- n8n workflow control
- No guardrails

### Demo Mode (Pepper)

Guardrailed access for customers:
- Equipment status (read-only)
- Fault diagnosis
- Procedure search
- Work order management
- Photo/video analysis
- Escalation to Mike

## Watchdog

Continuous monitoring system:

| Check | Frequency | Action |
|-------|-----------|--------|
| Node health | 5 min | Alert if down |
| Service status | 1 min | Auto-restart |
| Config drift | On change | Backup + alert |
| API keys | 15 min | Alert if invalid |
| Fingerprint | 5 min | Alert on structural change |

## Versioning

Every deployment is versioned with instant rollback:

```bash
/root/.pepper/
├── current -> versions/v1.2.0/    # Active version
├── previous -> versions/v1.1.2/   # Quick rollback
└── versions/
    ├── v1.0.0/
    ├── v1.1.0/
    ├── v1.1.2/
    └── v1.2.0/
```

Rollback to previous version in <30 seconds:
```bash
pepper rollback
```

## Development

### Running Locally

```bash
# Install dependencies
pip install -e .

# Run gateway
python -m pepper.gateway

# Run watchdog
python -m pepper.watchdog.main watchdog.yaml
```

### Testing

```bash
pytest -v
```

## Constitutional Compliance

PEPPER follows FactoryLM's constitutional principles:

- **Mission** - Ship products, generate revenue
- **Speed** - Fast routing, parallel execution
- **Proactive** - God Mode can act autonomously
- **Boundaries** - Demo Mode has hard guardrails
- **Human in Loop** - Demo escalates to Mike

## License

MIT - FactoryLM 2026
