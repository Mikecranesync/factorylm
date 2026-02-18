# 🏗️ ARCHITECTURE: Visual Computer Use Layer

> Defined 2026-02-04. This is a core component of the FactoryLM stack.

---

## Overview

Visual Computer Use (VCU) is the ability for AI to see screens and take actions. This is not a product — it's infrastructure for FactoryLM.

```
┌─────────────────────────────────────────────────────────────────┐
│                     FACTORYLM STACK                              │
├─────────────────────────────────────────────────────────────────┤
│  Layer 4: Human Interface                                        │
│  ├── Halo Glasses (voice + vision)                              │
│  ├── Telegram (text + voice)                                    │
│  └── Mobile App (future)                                        │
├─────────────────────────────────────────────────────────────────┤
│  Layer 3: Orchestration (Archimedes)                            │
│  ├── Task routing                                               │
│  ├── Agent coordination                                         │
│  └── Celery swarm                                               │
├─────────────────────────────────────────────────────────────────┤
│  Layer 2: VISUAL COMPUTER USE ← NEW                             │
│  ├── Screenshot capture                                         │
│  ├── Vision analysis (Claude/ShowUI)                            │
│  ├── Action execution (click/type/scroll)                       │
│  └── Human-in-the-loop approval                                 │
├─────────────────────────────────────────────────────────────────┤
│  Layer 1: Intelligence                                          │
│  ├── Claude API (cloud)                                         │
│  ├── ShowUI/UI-TARS (local, free)                               │
│  ├── Ollama (edge)                                              │
│  └── Mike's Brain (knowledge base)                              │
├─────────────────────────────────────────────────────────────────┤
│  Layer 0: Physical                                              │
│  ├── PLCs (Micro820, etc.)                                      │
│  ├── CMMS systems                                               │
│  ├── HMI screens                                                │
│  └── Industrial equipment                                       │
└─────────────────────────────────────────────────────────────────┘
```

---

## VCU Components

### 1. Screenshot Capture
- **Local:** PyAutoGUI, screencapture (Mac), scrot (Linux)
- **Remote:** Gradio live URL, WebSocket stream
- **Glasses:** Halo camera feed

### 2. Vision Analysis
| Model | Location | Cost | Latency |
|-------|----------|------|---------|
| Claude 3.5 | Cloud | ~$0.02/shot | 1-3s |
| GPT-4o | Cloud | ~$0.01/shot | 1-2s |
| ShowUI | Local GPU | FREE | 0.5-1s |
| UI-TARS | Local GPU | FREE | 0.5-1s |

### 3. Action Execution
```python
class VCUAction:
    CLICK = "click"      # x, y coordinates
    TYPE = "type"        # text string
    SCROLL = "scroll"    # direction, amount
    HOTKEY = "hotkey"    # key combination
    WAIT = "wait"        # milliseconds
```

### 4. Human-in-the-Loop
```
[AI proposes action]
    → Telegram: "Click 'Generate' button?"
    → [✅ Yes] [❌ No] [✏️ Edit]
    → Execute or revise
```

---

## Industrial Applications

### Use Case 1: HMI Navigation
```
Maintenance Tech: "Show me the conveyor status"
VCU: [Screenshots HMI] → [Finds conveyor page] → [Clicks] → [Returns screenshot]
```

### Use Case 2: CMMS Work Orders
```
Tech: "Create a work order for pump 7"
VCU: [Opens CMMS] → [Navigates to WO form] → [Fills fields] → [Submits]
```

### Use Case 3: PLC Programming
```
Tech: "Add a timer to rung 5"
VCU: [Opens CCW] → [Navigates to rung 5] → [Adds TON instruction] → [Configures]
```

---

## Implementation Priority

1. **Phase 1 (Now):** Install computer_use_ootb on Mike's laptops
2. **Phase 2 (This week):** Set up ShowUI for free local inference
3. **Phase 3 (Next week):** Integrate with Halo glasses
4. **Phase 4 (Month):** Production-ready industrial workflows

---

## Security Considerations

- VCU has full control of target machine — sandbox when possible
- Never expose Gradio public URLs without auth
- Log ALL actions for audit trail
- Human-in-the-loop for destructive actions

---

## References

- computer_use_ootb: https://github.com/showlab/computer_use_ootb
- ShowUI: https://github.com/showlab/ShowUI
- UI-TARS: https://github.com/bytedance/UI-TARS
- Claude Computer Use: https://platform.claude.com/docs/en/agents-and-tools/tool-use/computer-use-tool
- Paper: "The Dawn of GUI Agent" https://arxiv.org/abs/2411.10323

---

*This architecture is living documentation. Update as we learn.*
