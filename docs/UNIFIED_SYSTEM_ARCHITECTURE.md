# Unified System Architecture - FactoryLM Ecosystem

## Current State (February 2026)

This document describes the working architecture across three repositories orchestrated via Antfarm.

---

## Infrastructure Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           TAILSCALE MESH NETWORK                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────────────┐    ┌──────────────────────┐    ┌────────────────┐│
│  │  VPS (factorylm-prod)│    │ Travel Laptop        │    │ PLC Laptop     ││
│  │  100.68.120.99       │    │ 100.83.251.23        │    │ 100.72.2.99    ││
│  │                      │    │ (miguelomaniac)      │    │                ││
│  │  ┌────────────────┐  │    │                      │    │ ┌────────────┐ ││
│  │  │ RemoteMe API   │  │    │  ┌────────────────┐  │    │ │ Factory IO │ ││
│  │  │ :8100          │◄─┼────┼──│ Claude Code    │──┼────┼►│ Simulation │ ││
│  │  └────────────────┘  │    │  │ + Antfarm      │  │    │ └────────────┘ ││
│  │                      │    │  └────────────────┘  │    │                ││
│  │  ┌────────────────┐  │    │                      │    │ ┌────────────┐ ││
│  │  │ Friday Bot     │  │    │  ┌────────────────┐  │    │ │ Micro 820  │ ││
│  │  │ (Telegram)     │◄─┼────┼──│ Capabilities   │──┼────┼►│ PLC        │ ││
│  │  └────────────────┘  │    │  │ API Client     │  │    │ └────────────┘ ││
│  │                      │    │  └────────────────┘  │    │                ││
│  │  ┌────────────────┐  │    │                      │    │ ┌────────────┐ ││
│  │  │ n8n Workflows  │  │    │  ┌────────────────┐  │    │ │ Jarvis Node│ ││
│  │  │ (Automation)   │  │    │  │ FactoryLM      │  │    │ │ :8765      │ ││
│  │  └────────────────┘  │    │  │ Rivet-PRO      │  │    │ └────────────┘ ││
│  │                      │    │  │ Agent Factory  │  │    │                ││
│  │  ┌────────────────┐  │    │  └────────────────┘  │    └────────────────┘│
│  │  │ Master of      │  │    │                      │                      │
│  │  │ Puppets        │  │    └──────────────────────┘                      │
│  │  │ (Celery)       │  │                                                  │
│  │  └────────────────┘  │    ┌──────────────────────┐                      │
│  │                      │    │ Mobile (Telegram)    │                      │
│  │  ┌────────────────┐  │    │ Mike's Phone         │                      │
│  │  │ Flowise        │  │    │                      │                      │
│  │  │ (LLM Flows)    │  │    │  @FactoryLMBot       │                      │
│  │  └────────────────┘  │    │  @FridayAssistBot    │                      │
│  │                      │    │  @RivetProBot        │                      │
│  └──────────────────────┘    └──────────────────────┘                      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Running Services

### VPS (100.68.120.99)

| Service | Port | Status | Purpose |
|---------|------|--------|---------|
| RemoteMe API | 8100 | ✅ Running | Telegram webhook + node control |
| Friday Bot | - | ✅ Running | Personal assistant bot |
| n8n | 5678 | ✅ Running | Workflow automation |
| Flowise | 3000 | ✅ Running | LLM flow builder |
| Master of Puppets | - | ✅ Running | Celery task queue |
| Plane | 8000 | ✅ Running | Project management |

### Travel Laptop (100.83.251.23)

| Service | Port | Status | Purpose |
|---------|------|--------|---------|
| Claude Code | - | ✅ Active | Development + Antfarm |
| Jarvis Node | 8765 | ⚠️ On-demand | Remote control API |

### PLC Laptop (100.72.2.99)

| Service | Port | Status | Purpose |
|---------|------|--------|---------|
| Factory I/O | - | ✅ Available | PLC simulation |
| Micro 820 | Modbus | ✅ Connected | Real PLC hardware |
| Jarvis Node | 8765 | ⚠️ On-demand | Remote control API |

---

## Capability Matrix

### FactoryLM Capabilities API

```python
from services.capabilities import get_capabilities

caps = get_capabilities()

# Voice (ElevenLabs)
text = await caps.voice.transcribe(audio_bytes)
audio = await caps.voice.speak("Hello boss")

# GitHub
url = await caps.github.create_gist({"file.md": "content"})
issue = await caps.github.create_issue("factorylm", "Bug", "Details...")

# Memory (RAG)
results = await caps.memory.query("how did we handle X before?")
await caps.memory.add("user said X, bot responded Y")

# Nodes (multi-machine via Tailscale)
screenshot = await caps.nodes.screenshot("plc-laptop")
output = await caps.nodes.shell("travel-laptop", "git status")

# Photos (Vision OCR)
analysis = await caps.photos.analyze(image_bytes, "what equipment is this?")

# Factory (PLC Diagnosis)
diagnosis = await caps.factory.diagnose("why is conveyor stopped?")

# Telemetry
with caps.telemetry.span("operation_name"):
    ...
```

---

## Data Flow: Telegram → PLC Diagnosis

```
User (Phone)
    │
    │ "Why is the conveyor stopped?"
    ▼
┌─────────────────┐
│ Telegram API    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Friday Bot      │ (VPS)
│ friday_bot.py   │
└────────┬────────┘
         │ CapabilityClient.factory.diagnose()
         ▼
┌─────────────────┐
│ Factory         │ (VPS)
│ Capability      │
└────────┬────────┘
         │ HTTP → Jarvis Node
         ▼
┌─────────────────┐
│ PLC Laptop      │ (100.72.2.99)
│ Jarvis Node     │
└────────┬────────┘
         │ Read PLC tags
         ▼
┌─────────────────┐
│ Micro 820 PLC   │
│ or Factory I/O  │
└────────┬────────┘
         │ Tag values
         ▼
┌─────────────────┐
│ LLM Diagnosis   │ (Claude/Cosmos)
│ "Sensor E-STOP  │
│  is triggered"  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Telegram Reply  │
│ to User         │
└─────────────────┘
```

---

## Repository Responsibilities

### FactoryLM (Main Monorepo)
- **services/capabilities/** - Unified capability API
- **services/telegram/** - Bot implementations (Friday, PEPPER, Gus)
- **services/diagnosis/** - LLM diagnosis service
- **services/matrix/** - Tag ingestion and incidents
- **services/plc-modbus/** - PLC connection library
- **cosmos/** - NVIDIA Cosmos Reason 2 agent
- **my-ralph/** - Autonomous development loop

### Rivet-PRO (Industrial Maintenance)
- **rivet_pro/core/services/ocr_service.py** - Multi-provider vision OCR
- **rivet_pro/core/services/equipment_service.py** - CMMS equipment matching
- **rivet_pro/core/services/manual_service.py** - Manual search
- **rivet_pro/core/services/work_order_service.py** - Work order creation
- **rivet_pro/adapters/telegram/** - Telegram adapter

### Agent Factory (Content Production)
- **agent_factory/agents/** - 40+ specialized agents
- **agent_factory/integrations/telegram/** - Photo handler
- **agent_factory/tools/** - Research, Manus, OPCUA tools
- LangGraph pipelines for knowledge ingestion

---

## Antfarm Workflow Integration

### Installed Workflows

| Workflow | Repo | Purpose |
|----------|------|---------|
| `factorylm-feature-dev` | FactoryLM | Ralph autonomous development |
| `factorylm-incident-response` | FactoryLM | PLC fault → AI diagnosis → Telegram |
| `factorylm-repo-resurrection` | FactoryLM | Git forensics + repo recovery |
| `rivet-photo-to-manual` | Rivet-PRO | Photo OCR → Equipment → Manual |
| `rivet-work-order` | Rivet-PRO | Issue → Diagnosis → Work Order |
| `rivet-equipment-onboarding` | Rivet-PRO | Photo → DB → Manual import |
| `agentfactory-video-production` | Agent Factory | Research → Script → Video → Publish |
| `agentfactory-knowledge-ingestion` | Agent Factory | 7-stage atom pipeline |
| `agentfactory-committee-review` | Agent Factory | 5-committee weighted voting |

### Running Workflows

```bash
# List all workflows
node ~/.openclaw/workspace/antfarm/dist/cli/cli.js workflow list

# Run incident response
node ~/.openclaw/workspace/antfarm/dist/cli/cli.js workflow run factorylm-incident-response "Diagnose PLC fault on Line 3"

# Run photo-to-manual
node ~/.openclaw/workspace/antfarm/dist/cli/cli.js workflow run rivet-photo-to-manual "Analyze uploaded equipment photo"

# Monitor dashboard
# http://localhost:3333
```

---

## Environment Variables

### VPS (.env)
```bash
# Telegram
TELEGRAM_BOT_TOKEN=xxx
FRIDAY_BOT_TOKEN=xxx

# API Keys
OPENAI_API_KEY=xxx
ANTHROPIC_API_KEY=xxx
ELEVENLABS_API_KEY=xxx

# Database
SUPABASE_URL=xxx
SUPABASE_KEY=xxx

# Tailscale
TS_PLC_LAPTOP=100.72.2.99
TS_TRAVEL_LAPTOP=100.83.251.23
```

### Travel Laptop (.env)
```bash
ANTHROPIC_API_KEY=xxx
OPENAI_API_KEY=xxx
GITHUB_TOKEN=xxx
```

---

## Health Checks

```bash
# VPS services
curl http://100.68.120.99:8100/health  # RemoteMe
curl http://100.68.120.99:5678/        # n8n
curl http://100.68.120.99:3000/        # Flowise

# PLC Laptop (when Jarvis Node running)
curl http://100.72.2.99:8765/health

# Capabilities health (from any bot)
python -c "
from services.capabilities import get_capabilities
import asyncio
caps = get_capabilities()
print(asyncio.run(caps.health_check()))
"
```

---

## Quick Commands

```bash
# SSH to VPS
ssh root@100.68.120.99

# SSH to PLC laptop (PowerShell)
ssh hharp@100.72.2.99

# Check Tailscale status
tailscale status

# Restart Friday Bot (VPS)
ssh root@100.68.120.99 "systemctl restart friday-bot"

# View bot logs (VPS)
ssh root@100.68.120.99 "journalctl -u friday-bot -f"
```

---

## Next Steps

1. **Start Jarvis Nodes** on both laptops for full multi-machine control
2. **Integrate Antfarm dashboard** with Plane for project visibility
3. **Add webhook triggers** to n8n for automated workflow execution
4. **Enable Cosmos agent** for advanced PLC reasoning
