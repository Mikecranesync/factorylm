# Problem & Solution Narrative

## The Problem

95% of factories still run on "fix it when it breaks" maintenance. A pump fails, production stops, technicians scramble, and companies lose thousands per hour of downtime. The few factories that have predictive maintenance spent $500K+ on solutions from companies like Augury and Uptake.

These external monitoring systems bolt sensors onto existing equipment and watch from the outside. They're expensive, require new hardware installations, and fundamentally don't understand what's happening inside the machine's control system. They can tell you a motor is vibrating, but they can't tell you why or how to fix it.

The real problem isn't lack of data — PLCs (Programmable Logic Controllers) already collect everything. The problem is that this data stays trapped inside proprietary control systems, requiring specialized knowledge to interpret and act upon.

## Our Solution

FactoryLM puts AI directly inside PLCs — the brain of every factory machine. Instead of watching from outside, we integrate with the control layer itself, reading native sensor data and understanding the machine's actual state.

Our AI copilot doesn't just predict failures — it guides technicians through the exact repair process, learns from each incident, and converts successful interventions into deterministic code. This recursive learning approach transforms maintenance teams into experts and gradually reduces AI dependency.

Our 4-layer architecture flows intelligence downward:
- **Layer 3:** Cloud insights (optional)
- **Layer 2:** Local GPU processing (air-gapped)
- **Layer 1:** Edge LLM (Pi, real-time)
- **Layer 0:** Deterministic code + knowledge base (THE GOAL)

## Why This Works

At $30/device versus $500K+ deployments, we make AI-powered predictive maintenance accessible to every factory, not just Fortune 500 companies. We use existing PLC infrastructure, so there's no expensive sensor installation or system replacement required.

The PLC already knows everything — temperatures, pressures, motor speeds, valve positions. We just teach it to think about what that data means and help humans act on it.

When a technician fixes a conveyor belt issue guided by our AI, that solution becomes permanent code. The next time the same issue occurs, the PLC handles it automatically. Human expertise becomes machine capability.

This is how factories evolve from reactive to predictive to autonomous — not by replacing human knowledge, but by capturing and amplifying it.