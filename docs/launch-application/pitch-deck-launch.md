# LAUNCH Pitch Deck — FactoryLM

## Reframed: From "AI Copilot" to "Agent OS for Factories"

Adapted from YC deck (`docs/yc-application/pitch-deck-outline.md`). Same proof points, new framing: FactoryLM is an **autonomous agent platform** that runs inside factory control systems.

---

## Slide 1: Title

**Headline:** FactoryLM: The Agent OS Inside Factory PLCs

**Subhead:** Autonomous maintenance agents that live where the data is — inside the controller.

**Key message:** Not a dashboard. Not a bolt-on sensor. An operating system for factory intelligence that turns PLCs into self-diagnosing, self-dispatching machines.

---

## Slide 2: Problem

**Headline:** Factories Are Drowning in Data They Can't Use

- 95% of factories still run reactive maintenance ("fix it when it breaks")
- Unplanned downtime costs $2.8B annually across Fortune 500
- Existing solutions: $500K+ enterprise deployments, 12-18 month rollouts
- PLC data stays trapped — the controller knows what's wrong but can't tell anyone
- The maintenance workforce is aging out: 10,000 experienced techs retire monthly

**Reframe from YC deck:** Same stats, but emphasize the *agent gap* — factories have data, they need autonomous systems that act on it.

---

## Slide 3: Solution

**Headline:** Autonomous Agents Inside the Control Layer

- **Not a copilot — an agent OS.** Agents detect, triage, dispatch, and learn without human prompting
- Lives inside the PLC network, reads native sensor data at the source
- Dispatches the right technician with the right diagnosis in real-time
- Every fix gets recorded and converted into permanent code (intelligence flows downward)
- $30/device/month — accessible to every factory, not just Fortune 500

**Key differentiator from YC framing:** Copilot implies human-in-the-loop for every action. Agent OS means autonomous operation with human gates only on safety-critical decisions.

---

## Slide 4: How It Works — The Agent Stack

**Headline:** 5 Agents, 1 Pipeline, Zero Human Prompting

The Maintenance Dispatcher Pipeline (flagship workflow):

```
Alarm Monitor → Triager → WO Creator → Dispatcher → Resolution Tracker
     |              |           |            |              |
  PLC faults    KB match    CMMS Gist    Telegram      Learn + close
  via Modbus    + priority   work order   to tech       to Layer 0
```

**4-Layer Architecture** (same as YC deck):
- Layer 3: Cloud AI (optional, connected)
- Layer 2: Local GPU (70B models, air-gapped)
- Layer 1: Edge LLM (Pi, real-time)
- Layer 0: Deterministic code + KB (THE GOAL)

**Agent workflows defined as antfarm YAMLs** — version-controlled, reproducible, auditable.

---

## Slide 5: Market

**Headline:** $91B Market, 95% Untouched

- **TAM:** $91B predictive maintenance by 2033 (29.4% CAGR)
- **SAM:** $225M-750M (50K US facilities x 15-50 devices x $30)
- **SOM:** $360K Year 1 → $37.8M Year 5
- Manufacturing labor shortage creates urgency: fewer techs = more need for agents
- Industry 4.0 adoption accelerating but most solutions are still dashboards, not agents

---

## Slide 6: Traction

**Headline:** Working Prototype, Real Factory Data, 9 Days to Production

- Allen-Bradley Micro820 PLC integration: Modbus TCP verified and working
- Edge device v2.0 deployed with auto-network detection
- 9,554 messages of human-AI collaboration documented
- Production CMMS (GitHub Gist work orders) processing real maintenance data
- 3 antfarm agent workflows defined and spec'd (maintenance, robot advisor, ops reporter)
- Tony agent swarm operational: 3 active sub-agents across Tailscale mesh

**New since YC application:** Agent workflows, memory architecture, multi-agent orchestration.

---

## Slide 7: Competition

**Headline:** They Watch From Outside. We Think From Inside.

| Dimension | Enterprise (Augury, Uptake) | SaaS CMMS (Fiix, UpKeep) | FactoryLM |
|-----------|---------------------------|--------------------------|-----------|
| Cost | $500K+ | $20-75/user/mo | $30/device/mo |
| AI location | Cloud only | None (reactive) | Edge + PLC native |
| Deployment | 12-18 months | Weeks | Hours |
| Autonomy | Dashboard alerts | Work order tracking | Autonomous agents |
| Learning | Static models | None | Recursive → code |
| Connectivity | Internet required | Internet required | Works offline |

**New column vs YC deck:** "vs generic AI agents" — Devin, Replit Agent, etc. build software. FactoryLM agents operate machinery. Different domain, different safety requirements, different moat.

---

## Slide 8: Business Model

**Headline:** $30/Device/Month, 85% Gross Margin, 9:1 LTV/CAC

- SaaS: $30/device/month, 3-year average lifetime
- Target: 15-50 devices per facility ($450-$1,500/mo per customer)
- Unit economics: $2,400 CAC, $21,600 LTV, 9:1 ratio
- Customer ROI: 15-30% maintenance cost reduction pays for deployment in 3-6 months
- Expansion revenue: more devices per factory + additional agent workflows (robot advisor, ops reporter)

---

## Slide 9: Team

**Headline:** 15 Years Inside Factories + AI Agent Architecture

- **Mike Crane:** 15+ years PLC programming, maintenance management, factory operations. Ladder Logic, Structured Text, Function Block Diagrams, Modbus networks. Built the problem, now building the solution.
- **Agent Swarm:** Tony (orchestrator), Ultron (cloud reasoning), Jarvis (edge/PLC), Gus (factory floor). 24/7 development and operations capability.
- **Industrial Skills Hub:** YouTube channel building the maintenance community.

**Unfair advantage:** Domain expertise that takes a decade to acquire + AI acceleration from day one.

---

## Slide 10: The Ask

**Headline:** $500K to Deploy Agents in 3 Factories

**Use of funds:**
- 3 factory beta deployments (automotive, aerospace, food/bev)
- Expand from Micro820 to ControlLogix (enterprise-grade PLCs)
- Manufacture 50 edge devices for customer pilots
- Deploy pgvector memory layer (episodic + semantic + playbook)
- First paying customers at $30/device by month 6

**Milestones:**
- Month 1-2: pgvector deployed, maintenance-dispatcher workflow running autonomously
- Month 3-4: First factory beta live, collecting real episodes
- Month 5-6: 50 devices deployed, first revenue, playbook cards generating
- Month 12: 250 devices, $90K ARR, Series A positioning

---

## Appendix: Key Differences from YC Deck

| Aspect | YC Deck | LAUNCH Deck |
|--------|---------|-------------|
| Framing | AI Copilot | Agent OS |
| Autonomy | Human-in-the-loop | Autonomous with human gates |
| Architecture | 4-layer stack | 4-layer stack + antfarm workflows |
| Traction | Working prototype | Prototype + agent swarm + memory arch |
| Competition | vs sensors | vs sensors + vs generic AI agents |
| Demo | PLC read/write | Full alarm → dispatch → resolution pipeline |

---

## Design Guidelines

- **Color palette:** Industrial blues (#1E3A8A), agent green (#22C55E), safety orange (#F97316)
- **Typography:** Bold headers, Inter/Roboto sans-serif
- **Visual style:** Technical precision, agent flow diagrams, real factory photos
- **Demo:** Live Micro820 alarm → Tony dispatch → Telegram notification (3 minutes)
