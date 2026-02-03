# PLC Service Adapters - Comparison

## Background

Two "PLC Copilot" implementations were developed independently by different Claude instances.
This document tracks both until one is deprecated.

**Date Created:** 2026-01-30
**Decision Pending:** Evaluate both over production usage period

---

## Adapter 1: plc-copilot (Photo→CMMS)

- **Path:** `services/plc-copilot/`
- **Source:** Rivet-PRO / `/opt/plc-copilot/`
- **Function:** Telegram bot receives equipment photos, uses Gemini Vision to analyze defects, creates CMMS work orders automatically
- **Stack:** Python, Telegram API, Gemini Vision AI, CMMS REST API

### Key Features
- Photo intake via Telegram
- AI-powered defect detection
- Automatic work order creation
- Priority classification (LOW/MEDIUM/HIGH)
- Asset identification

### Architecture
```
Telegram → Bot → Gemini Vision → CMMS API
   📸        🤖       👁️            📋
```

---

## Adapter 2: plc-modbus (Hardware Integration)

- **Path:** `services/plc-modbus/`
- **Source:** [factorylm-plc-client](https://github.com/Mikecranesync/factorylm-plc-client)
- **Function:** Direct Modbus TCP communication with Allen-Bradley Micro 820 PLC, real-time I/O monitoring, Factory I/O simulation
- **Stack:** Python, pymodbus, FastAPI, Raspberry Pi edge device

### Key Features
- Direct PLC hardware control via Modbus TCP
- Real-time I/O state monitoring
- Network scanner for PLC discovery
- Raspberry Pi edge device integration
- LLM-powered Structured Text (ST) code generation

### Architecture
```
FastAPI ← → Modbus TCP ← → Allen-Bradley PLC
   🖥️           📡              🏭
              ↕
         Raspberry Pi Edge
              🥧
```

---

## Comparison

| Aspect | plc-copilot | plc-modbus |
|--------|-------------|------------|
| **Input** | Photos via Telegram | Direct PLC hardware |
| **Output** | CMMS work orders | I/O state, control signals |
| **AI Integration** | Gemini Vision (image analysis) | LLM (ST code generation) |
| **Hardware Required** | None (cloud-only) | Allen-Bradley PLC, optional Raspberry Pi |
| **Primary Use Case** | Field technician photo submission | Shop floor automation control |
| **User Interface** | Telegram bot | FastAPI REST + CLI tools |

---

## They're Actually Complementary

After analysis, these adapters serve **different purposes**:

- **plc-copilot**: Maintenance workflow (photos → work orders)
- **plc-modbus**: Automation control (LLM → PLC commands)

They could work together:
1. `plc-modbus` detects equipment anomaly via PLC sensors
2. Triggers `plc-copilot` to create maintenance work order
3. Field tech photos feed back into system

---

## Resolution Plan

1. ✅ Both adapters added to monorepo
2. ⏳ Evaluate over production usage
3. ⏳ Determine if they should merge, stay separate, or one deprecated
4. ⏳ Final decision based on: production stability, user adoption, maintenance burden

### Decision Criteria
- [ ] Which adapter sees more production usage?
- [ ] Are they truly solving the same problem?
- [ ] Can they be integrated into a unified workflow?
- [ ] Which has lower maintenance burden?

---

## History

| Date | Event |
|------|-------|
| 2026-01-25 | plc-copilot migrated from Rivet-PRO |
| 2026-01-30 | plc-modbus discovered in separate repo |
| 2026-01-30 | This comparison document created |
| TBD | Final decision on adapter strategy |
