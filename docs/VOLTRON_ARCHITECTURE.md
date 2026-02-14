# Voltron Architecture — Factory LM Matrix + Nodes

**Version:** 0.1 (Draft)  
**Author:** Mike Harper  
**Date:** 2026-02-12  
**Status:** PLANNING — Not yet implemented

---

## The One-Liner

**Voltron is a distributed industrial AI system where a central Matrix dispatches tasks to autonomous Nodes — each with immutable identity and safety policies — using tiered LLM intelligence that defaults to the cheapest model that can do the job.**

---

## Core Concepts

### Matrix (Central Controller)

The Matrix is the brain. It runs on a VPS (primary: DigitalOcean) and handles:

- **Telegram bot** — sole operator interface (v0.1)
- **Node registry** — tracks all nodes, their capabilities, health, and policies
- **LLM router** — picks the right model tier for each task
- **Conversation memory** — persistent context in Postgres
- **Task dispatch** — sends work to the right node based on capability
- **Observability** — aggregates traces and logs from all nodes

The Matrix does NOT talk to PLCs directly. It delegates to Nodes.

### Nodes (Distributed Agents)

A Node is anything that can receive a task and execute it. Two types:

| Type | Examples | Runs On |
|------|----------|---------|
| **Hardware Node** | PLC reader, sensor monitor, camera | Raspberry Pi, Jetson, industrial PC |
| **Software Node** | Code analyzer, doc searcher, web scraper | VPS process, laptop process |

Every Node has:

1. **Soul file** (`soul.md`) — identity, personality, role description. **Immutable by LLM.**
2. **Policy file** (`policy.yaml`) — allowed tools, PLC addresses, rate limits, escalation rules. **Immutable by LLM.**
3. **Local tools** — functions the node can execute (read PLC, query DB, etc.)
4. **Local storage** — SQLite for logs, cache, and offline operation
5. **Heartbeat** — periodic check-in with Matrix

```
┌─────────────────────────────────────────────────────────────────┐
│                         MATRIX (VPS)                            │
│                                                                 │
│  ┌───────────┐  ┌───────────┐  ┌──────────┐  ┌──────────────┐  │
│  │ Telegram  │  │   LLM     │  │   Node   │  │  Postgres    │  │
│  │   Bot     │──│  Router   │──│ Registry │──│  (memory,    │  │
│  │           │  │           │  │          │  │   state)     │  │
│  └───────────┘  └───────────┘  └──────────┘  └──────────────┘  │
│                       │                                         │
└───────────────────────┼─────────────────────────────────────────┘
                        │ task dispatch / results
          ┌─────────────┼──────────────┐
          │             │              │
          ▼             ▼              ▼
   ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
   │  Node: PLC  │ │ Node: VPS   │ │ Node: Laptop│
   │  (Micro820) │ │ (software)  │ │ (dev/test)  │
   │             │ │             │ │             │
   │ soul.md     │ │ soul.md     │ │ soul.md     │
   │ policy.yaml │ │ policy.yaml │ │ policy.yaml │
   │ tools: [    │ │ tools: [    │ │ tools: [    │
   │  read_plc,  │ │  search_kb, │ │  read_plc,  │
   │  read_io    │ │  run_diag   │ │  search_kb  │
   │ ]           │ │ ]           │ │ ]           │
   │ SQLite      │ │ SQLite      │ │ SQLite      │
   └─────────────┘ └─────────────┘ └─────────────┘
```

---

## LLM Model Tiering

Two tiers. The router picks the cheapest one that can handle the task.

| Tier | Codename | Models | Use Case | Cost |
|------|----------|--------|----------|------|
| **Tier 2** | Big Brain | Claude Opus, GPT-4 class | Novel problems, complex diagnostics, design decisions | $$$  |
| **Tier 1** | Small Brain | Claude Sonnet/Haiku, Groq Llama 3.3 70B, local models | Routine queries, command translation, status checks | $ or free |

### Routing Rules

```python
def pick_tier(task):
    # Default: small brain
    tier = "small"

    # Escalate to big brain only when needed
    if task.requires_multi_step_reasoning:
        tier = "big"
    if task.novel and not task.matches_known_pattern:
        tier = "big"
    if task.explicitly_requested_by_operator:
        tier = "big"
    if task.safety_critical_analysis:
        tier = "big"

    return tier
```

### Cost Strategy

- **Runtime default = Tier 1 (Small Brain).** Most factory queries are repetitive.
- **Tier 2 (Big Brain) requires explicit escalation** — either the operator asks for it, or the small brain flags uncertainty.
- **Layer 0 first** — before any LLM, check the knowledge base. If there's a known answer, return it instantly at zero cost.
- **Track spend** — every LLM call logs provider, model, tokens, cost. Matrix dashboard shows daily/weekly burn.

### Provider Configuration

All providers configured via `config/models.yaml`, never hardwired:

```yaml
providers:
  anthropic:
    api_key_env: ANTHROPIC_API_KEY
    models:
      big: claude-opus-4-5-20250514
      small: claude-sonnet-4-20250514

  groq:
    api_key_env: GROQ_API_KEY
    models:
      small: llama-3.3-70b-versatile

  google:
    api_key_env: GOOGLE_API_KEY
    models:
      small: gemini-2.5-flash

  local:
    base_url: http://localhost:11434
    models:
      small: qwen2.5:0.5b

default_tier: small
default_provider: groq
fallback_chain: [groq, anthropic, google, local]
```

---

## Node Safety Model

### Immutable Files

Two files per node that the LLM cannot modify, even if instructed to:

**`soul.md`** — WHO the node is:
```markdown
# Node: PLC-Reader-Alpha
Role: Industrial PLC data reader
Personality: Precise, cautious, reports anomalies immediately
Owner: Mike Harper
Created: 2026-02-12
```

**`policy.yaml`** — WHAT the node is ALLOWED to do:
```yaml
node_id: plc-reader-alpha
allowed_tools:
  - read_coils
  - read_holding_registers
  - read_input_registers
denied_tools:
  - write_coil          # READ-ONLY — never write to PLC
  - write_register      # READ-ONLY — never write to PLC
  - execute_shell       # No shell access
plc_access:
  addresses: [192.168.1.100]
  protocols: [modbus_tcp]
  mode: read_only       # Enforced at tool level
rate_limits:
  max_plc_reads_per_minute: 60
  max_llm_calls_per_minute: 10
escalation:
  on_unknown_fault: notify_matrix
  on_safety_event: notify_matrix_urgent
```

### Enforcement

Policy is enforced **at the node**, not at the Matrix. This means:

1. Even if Matrix sends a `write_coil` task, the node refuses it locally.
2. Even if the LLM hallucinates a tool call, the policy engine blocks it.
3. The node logs every policy violation and notifies Matrix.

```
Task arrives → Policy engine checks → Allowed? → Execute
                                    → Denied?  → Log + reject + notify Matrix
```

### Read-Only PLC Constraint

Inherited from FactoryLM. Voltron nodes **never write to PLCs.**

```
✓ Read tag values        ✗ Write to PLCs
✓ Monitor I/O states     ✗ Change setpoints
✓ Record fault codes     ✗ Start/stop equipment
✓ Analyze trends         ✗ Modify programs
✓ Suggest actions        ✗ Execute actions
```

---

## Telegram Integration

Telegram is the sole operator interface for v0.1.

### Message Flow

```
Operator sends message
        │
        ▼
┌─────────────────┐
│  Telegram Bot   │  (python-telegram-bot or aiogram)
│  (in Matrix)    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Message Router │  Classifies intent, picks node + tier
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
 Node A    Node B    (parallel if needed)
    │         │
    └────┬────┘
         │
         ▼
┌─────────────────┐
│  Response       │  Aggregated, formatted
│  Composer       │
└────────┬────────┘
         │
         ▼
  Operator receives reply
```

### Bot Commands (v0.1)

| Command | Action |
|---------|--------|
| `/status` | Show all nodes, health, last heartbeat |
| `/plc` | Read current PLC state from PLC node |
| `/ask <question>` | Route question through intelligence stack |
| `/nodes` | List registered nodes and capabilities |
| `/cost` | Show LLM spend (today, this week) |
| `/brain <big/small>` | Force next query to use specific tier |

---

## Data Storage

| Where | Engine | What's Stored |
|-------|--------|---------------|
| **Matrix** | PostgreSQL | Conversation history, node registry, task log, LLM cost tracking, knowledge base index |
| **Each Node** | SQLite | Local tool results cache, heartbeat log, policy violation log, offline task queue |

### Why Both?

- Postgres on Matrix = single source of truth, queryable, backed up.
- SQLite on nodes = nodes can operate offline, cache results, and sync when reconnected.

---

## Day-1 Nodes

| Node ID | Type | Runs On | Tools | Purpose |
|---------|------|---------|-------|---------|
| `plc-micro820` | Hardware (software proxy) | Laptop (connects to PLC via Modbus TCP) | `read_coils`, `read_holding_registers` | Read Micro 820 PLC state |
| `vps-worker` | Software | DigitalOcean VPS | `search_kb`, `run_diagnostic`, `web_search` | General-purpose reasoning node |
| `dev-local` | Software | Laptop | All tools (dev mode) | Development and testing |

Phase 2 adds: Raspberry Pi hardware node, Jetson vision node.

---

## Deployment

### Matrix (DO VPS)

```
systemd service: voltron-matrix
Port: 8443 (webhook) or polling mode
Config: /etc/voltron/matrix.yaml
DB: PostgreSQL (Neon or local)
Logs: /var/log/voltron/matrix.log
Traces: Honeycomb (OTel SDK)
```

### Nodes

```
systemd service: voltron-node (on Linux)
Scheduled Task / NSSM service (on Windows)
Config: ~/.voltron/node.yaml
Soul: ~/.voltron/soul.md (read-only)
Policy: ~/.voltron/policy.yaml (read-only)
DB: ~/.voltron/local.db (SQLite)
```

---

## What Voltron Is NOT

- **Not a control system.** Read-only. Suggests actions, never executes them on equipment.
- **Not a replacement for clawdbot.** Clawdbot stays separate. May retire later.
- **Not cloud-dependent.** Nodes work offline. Matrix can run on a laptop for dev.
- **Not locked to Anthropic.** Any LLM provider works via config. Groq free tier is the default.

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 0.1 | 2026-02-12 | Initial architecture draft |
