# Autonomous PLC Server - FactoryLM

**Goal:** PLC laptop runs autonomously as a Factory I/O simulation server with AI feedback loop.

## Hardware
- **PLC Laptop:** Quadro P620 GPU, Windows, Ollama capable
- **Factory I/O:** 3D industrial simulation software
- **Micro820 PLC:** Allen-Bradley controller

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   PLC LAPTOP                        │
├─────────────────────────────────────────────────────┤
│  ┌──────────────┐    ┌──────────────┐              │
│  │ Factory I/O  │◄──►│  Micro820    │              │
│  │ (Simulation) │    │  (Real PLC)  │              │
│  └──────┬───────┘    └──────────────┘              │
│         │                                           │
│         ▼                                           │
│  ┌──────────────┐    ┌──────────────┐              │
│  │ Screen Cap   │───►│ Claude/Ollama│              │
│  │ (Vision AI)  │    │ (Analysis)   │              │
│  └──────────────┘    └──────────────┘              │
│         │                                           │
│         ▼                                           │
│  ┌──────────────┐                                  │
│  │ Jarvis Node  │◄────── VPS Commands              │
│  └──────────────┘                                  │
└─────────────────────────────────────────────────────┘
```

## Options for Vision Feedback

### Option 1: Screen Capture + Vision AI (Simple)
- Capture Factory I/O window periodically
- Send to Claude/Gemini Vision for analysis
- "What's happening? Any faults? Conveyor status?"

### Option 2: Factory I/O OPC-UA (Elegant)
- Factory I/O supports OPC-UA server
- Read simulation data directly (no vision needed)
- Real-time tag values like a real PLC

### Option 3: Hybrid
- OPC-UA for data, Vision for anomaly detection
- Best of both worlds

## Setup Steps

1. [ ] Install Jarvis Node on PLC laptop
2. [ ] Connect to VPS hub (100.68.120.99:8765)
3. [ ] Install Ollama with llama3.2 + llava
4. [ ] Configure Factory I/O OPC-UA server
5. [ ] Create FactoryLM adapter for Factory I/O
6. [ ] Test autonomous loop

## Files
- `jarvis_node_plc.py` - Node agent for PLC laptop
- `factoryio_adapter.py` - OPC-UA client for Factory I/O
- `vision_monitor.py` - Screen capture + AI analysis
- `autonomous_loop.py` - Main orchestration

## Tags
- `v0.1-autonomous-plc` - Initial setup
- Branch: `feature/autonomous-plc-server`
