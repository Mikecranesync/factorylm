# FactoryLM

**Industrial AI Platform — The Vision**

**Version:** 0.25  
**Author:** Mike Harper  
**Status:** CANONICAL — This document IS the vision. Everything references this.  
**Last Updated:** February 3, 2026

---

## ⚠️ READ THIS FIRST

This README IS the vision statement for FactoryLM.

**For AI agents:** Read this at the start of EVERY session. Do not propose ideas that contradict this. Do not rediscover these concepts as if they are new.

**For developers:** Every PR moves toward this architecture. When in doubt, reference this document.

**When Mike says "update the README":** You update THIS VISION.

---

## The One-Liner

**FactoryLM is a tiered intelligence system that pushes knowledge as close to the edge as possible, using deterministic code for common tasks and escalating to AI only when necessary.**

---

## Core Philosophy

### Intelligence Flows Downward

The goal is NOT to use more AI. The goal is to use LESS AI over time.

```
Day 1:   Query → Cloud AI (Claude) → Answer
Day 30:  Same query → Pattern recognized → Workflow created  
Day 60:  Same query → Code executes → Instant answer (no AI)
```

Every trace, every workflow, every observation pushes intelligence DOWN the stack.

---

## The Stack

```
┌─────────────────────────────────────────────────────────────┐
│  LAYER 3: CLOUD AI                                          │
│  Claude, GPT-4, etc.                                        │
│  Complex reasoning, novel problems                          │
│  Response: 1-2 seconds | Cost: $0.01-0.10                   │
│  OPTIONAL — Customer chooses based on security needs        │
├─────────────────────────────────────────────────────────────┤
│  LAYER 2: LOCAL GPU SERVER                                  │
│  Llama 70B, Mixtral, etc.                                   │
│  Medium complexity, diagnostics, analysis                   │
│  Response: 2-3 seconds | Cost: Electricity only             │
│  AIR-GAPPED — No internet required                          │
├─────────────────────────────────────────────────────────────┤
│  LAYER 1: EDGE LLM (Raspberry Pi)                           │
│  Qwen 0.5B, Llama 1B, Phi-2                                 │
│  Simple NL parsing, command translation                     │
│  Response: 0.5-1 second | Cost: None                        │
│  ON-DEVICE — Runs on the Pi itself                          │
├─────────────────────────────────────────────────────────────┤
│  LAYER 0: DETERMINISTIC CODE + KNOWLEDGE BASE               │
│                                                             │
│  Components:                                                │
│  • Vector DB — Semantic search over all documentation       │
│  • Plane — Workflow orchestration and task management       │
│  • Wiseflow — Automated knowledge gathering and indexing    │
│  • Logic Gates — Pattern-matched responses from manuals     │
│  • Workflows — Captured from successful AI interactions     │
│                                                             │
│  Response: <100ms | Cost: None                              │
│  THIS IS WHERE WE WANT EVERYTHING TO END UP                 │
└─────────────────────────────────────────────────────────────┘
```

**Layer 0 is the goal.** Everything else is fallback.

---

## User Interfaces

Users interact via their preferred platform:

### Primary (Must Work First)
- **WhatsApp** — Primary channel, especially Latin America
- **Phone** — Standard messaging interface

### Secondary  
- **Telegram** — Power users, developers
- **Slack** — Enterprise teams
- **Halo Glasses** — Hands-free on factory floor
- **Web Dashboard** — Admin and analytics

### All Adapters Are Dumb

```
┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│ WhatsApp │ │ Telegram │ │  Slack   │ │  Phone   │ │   Halo   │
│ Adapter  │ │ Adapter  │ │ Adapter  │ │ Adapter  │ │ Adapter  │
└────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘
     │            │            │            │            │
     └────────────┴────────────┼────────────┴────────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │   Message Router    │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │  Intelligence Stack │
                    │    (Layers 0-3)     │
                    └─────────────────────┘
```

Adapters handle I/O ONLY. All intelligence lives in the core.

---

## Layer 0: The Knowledge Engine

This is NOT AI. This is CODE. It's fast. It's free. It's reliable.

### Components

| Component | Purpose |
|-----------|---------|
| **Vector DB** | Semantic search over every manual, guide, fault code |
| **Plane** | Workflow orchestration, task planning, project management |
| **Wiseflow** | Automated knowledge gathering, web scraping, indexing |
| **Logic Gates** | Pattern-matched responses built from observed AI interactions |
| **Workflow Engine** | Multi-step processes captured from successful troubleshooting |

### What's In The Knowledge Base

- Every equipment manual ever created (parsed, indexed)
- Every troubleshooting guide (vectorized for semantic search)
- Every PLC fault code with known solutions
- Historical maintenance records
- Technician feedback and corrections

### The Rivet Pro Process

When a technician encounters equipment:

1. **Identify** — OCR/barcode/RFID reads tag
2. **Gather** — Rivet Pro fetches ALL available knowledge
3. **Store** — Vectorize, index, tag in knowledge base
4. **Deliver** — Semantic search returns instant answer
5. **Learn** — New info captured, gaps identified and filled

**No LLM required for known information.**

---

## Routing Logic

```python
def route_query(query, context):
    # LAYER 0: Knowledge base first (instant, free)
    kb_result = knowledge_base.search(query)
    if kb_result.confidence > 0.9:
        return kb_result
    
    # LAYER 0: Check for matching workflow
    workflow = plane.match_workflow(query)
    if workflow:
        return workflow.execute()
    
    # LAYER 1: Edge LLM for simple commands
    if is_simple_command(query):
        return edge_llm.process(query)
    
    # LAYER 2: Local GPU for medium complexity
    if gpu_server.available:
        return gpu_server.process(query)
    
    # LAYER 3: Cloud as last resort
    if cloud.available and not air_gapped:
        return cloud.process(query)
```

---

## The Observability Loop

Every query is traced. Patterns become code.

```
Query → Trace Logged → Pattern Found → Workflow Created → Layer 0 Grows
```

### Tools
- **LangSmith** — LLM interaction tracing
- **Phoenix** — Observability and debugging
- **Custom Logging** — Business-specific metrics

### Metrics We Track
- Queries per layer (should shift toward Layer 0)
- Average response time (should decrease)
- Cost per query (should decrease)
- Knowledge base coverage (should increase)

---

## Hardware Architecture

### FactoryLM Edge (Raspberry Pi 4)

```
┌─────────────────────────────────────────────────────────┐
│                 FactoryLM Edge                          │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │   Modbus    │  │  EtherNet/  │  │   OPC UA    │     │
│  │   TCP/RTU   │  │     IP      │  │   Client    │     │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘     │
│         └────────────────┼────────────────┘             │
│                          ▼                              │
│                 ┌─────────────────┐                     │
│                 │   Tag Engine    │                     │
│                 └────────┬────────┘                     │
│         ┌────────────────┼────────────────┐             │
│         ▼                ▼                ▼             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │  Vector DB  │  │  Edge LLM   │  │  Workflow   │     │
│  │  (Layer 0)  │  │  (Layer 1)  │  │   Engine    │     │
│  └─────────────┘  └─────────────┘  └─────────────┘     │
│                          │                              │
│                          ▼                              │
│                 ┌─────────────────┐                     │
│                 │   API Server    │                     │
│                 └─────────────────┘                     │
└─────────────────────────────────────────────────────────┘
```

### Supported Protocols

| Protocol | Devices |
|----------|---------|
| Modbus TCP/RTU | Universal |
| EtherNet/IP | Allen-Bradley |
| Siemens S7 | S7-300/400/1200/1500 |
| OPC UA | Universal |

### Hardware Packs (Accessories)

| SKU | Contents | Purpose |
|-----|----------|---------|
| AP-4 | 4-ch 4-20mA module | Analog I/O |
| AP-8 | 8-ch 4-20mA module | Analog I/O |
| PP-1 | I/P + P/I transducers | Pneumatic |
| SP-2 | RS-232/485 converters | Legacy serial |
| IO-8 | 8-ch mixed I/O | Digital I/O |

---

## Deployment Scenarios

### A: Full Stack (Internet Available)
All layers available. Maximum intelligence.

### B: Air-Gapped (Defense/ITAR)  
Layer 3 disabled. 70B local model. Data never leaves facility.

### C: Budget (No GPU Server)
Skip Layer 2. Pi + Cloud only.

### D: Maximum Security (Pi Only)
Layer 0 only. Completely isolated.

---

## Read-Only Constraint

FactoryLM is a **diagnostic tool**, not a control system.

```
✓ Read tag values        ✗ Write to PLCs
✓ Monitor I/O states     ✗ Change setpoints  
✓ Record fault codes     ✗ Start/stop equipment
✓ Analyze trends         ✗ Modify programs
✓ Suggest actions        ✗ Execute actions
```

**Why:** Eliminates fear, simplifies IT approval, removes liability.

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 0.25 | 2026-02-03 | Initial canonical vision document |

---

## References

This document must be referenced by:
- Every `CLAUDE.md` file
- Every `AGENTS.md` file  
- Every `.github/copilot-instructions.md`
- Root README of every FactoryLM repo

**When Mike says "update the README" — update THIS VISION.**

---

**FactoryLM — AI for the Factory Floor**
