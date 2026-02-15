# PEPPER SYSTEM PRD

**Product Requirements Document**
**Version:** 1.0
**Author:** AI Architect (Claude) + Mike Harper
**Status:** DRAFT — Awaiting Approval
**Created:** 2026-02-14

---

## Executive Summary

**PEPPER** is a dual-mode Telegram bot system that provides:
- **God Mode** (PEPPER PRIME) — Full system access for Mike
- **Demo Mode** (PEPPER DEMO) — Guardrailed access for technicians/customers

This replaces the current fragmented bot landscape (JARVIS, FRIDAY, GUS, Clawdbot) with a unified architecture that follows FactoryLM's constitutional principles and intelligence layer philosophy.

---

## 1. THE VISION (Aligned with README.md)

### 1.1 Intelligence Flows Downward

PEPPER follows the 4-layer intelligence stack:

```
┌─────────────────────────────────────────────────────────────────────┐
│  LAYER 3: CLOUD AI (Claude Opus, GPT-4o)                            │
│  • Novel diagnosis, complex reasoning                               │
│  • God Mode: Unrestricted access                                    │
│  • Demo Mode: Factory questions only                                │
│  • Latency: 2-10s | Cost: $$$                                       │
├─────────────────────────────────────────────────────────────────────┤
│  LAYER 2: LOCAL LLM (Groq Llama 70B, DeepSeek R1)                  │
│  • Pattern matching, known faults                                   │
│  • Primary model for both modes                                     │
│  • Latency: 0.5-2s | Cost: $ (or free)                             │
├─────────────────────────────────────────────────────────────────────┤
│  LAYER 1: EDGE LLM (Qwen 0.5B on Pi)                               │
│  • Real-time classification                                         │
│  • "Is this normal?" decisions                                      │
│  • Latency: 50-200ms | Cost: Free                                  │
├─────────────────────────────────────────────────────────────────────┤
│  LAYER 0: DETERMINISTIC CODE + KNOWLEDGE BASE                       │
│  • Rule engine, lookup tables                                       │
│  • "Motor temp > 80°C = shutdown"                                   │
│  • THE GOAL: Move everything here                                   │
│  • Latency: <10ms | Cost: Zero                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.2 Constitutional Alignment

PEPPER adheres to the FactoryLM Constitution:

| Article | PEPPER Implementation |
|---------|----------------------|
| I. Mission | Ship products, generate revenue — PEPPER enables demos and customer support |
| II. Speed | Fast routing, parallel tool calls, no unnecessary confirmations |
| III. Proactive | God Mode can act autonomously; Demo Mode waits for commands |
| IV. One-Team | All PEPPER instances share context via session storage |
| V. Boundaries | Demo Mode has hard guardrails; God Mode is unrestricted |
| VI. Quality | Comprehensive logging, audit trails, error recovery |
| VII. Transparency | All actions logged, no hidden behaviors |
| VIII. Improvement | Learning loop captures patterns for Layer 0 |
| IX. Human in Loop | Demo Mode escalates to Mike; God Mode IS Mike |
| X. Long Game | Durable architecture, maintainable code |

---

## 2. ARCHITECTURE

### 2.1 System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         TELEGRAM CLOUD                              │
│                                                                     │
│  ┌───────────────────┐              ┌───────────────────┐          │
│  │  @PepperPrimeBot  │              │  @FactoryLMBot    │          │
│  │   (God Mode)      │              │   (Demo Mode)     │          │
│  │   Mike Only       │              │   Public/Beta     │          │
│  └─────────┬─────────┘              └─────────┬─────────┘          │
│            │                                   │                    │
└────────────┼───────────────────────────────────┼────────────────────┘
             │                                   │
             └──────────────┬────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      VPS (100.68.120.99)                            │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    PEPPER GATEWAY                            │   │
│  │                                                              │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │   │
│  │  │ Auth Router  │  │ Mode Loader  │  │ Tool Router  │       │   │
│  │  │ user_id →    │  │ god/demo     │  │ skill →      │       │   │
│  │  │   mode       │  │   config     │  │   handler    │       │   │
│  │  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘       │   │
│  │         └─────────────────┼─────────────────┘                │   │
│  │                           │                                  │   │
│  │                           ▼                                  │   │
│  │  ┌─────────────────────────────────────────────────────┐    │   │
│  │  │               PERSONA ENGINE                         │    │   │
│  │  │                                                      │    │   │
│  │  │  SOUL.md → Personality, Voice, Boundaries            │    │   │
│  │  │  TOOLS.md → Available capabilities per mode          │    │   │
│  │  │  MEMORY.md → Session context, user preferences       │    │   │
│  │  └─────────────────────────────────────────────────────┘    │   │
│  │                           │                                  │   │
│  │                           ▼                                  │   │
│  │  ┌─────────────────────────────────────────────────────┐    │   │
│  │  │               INTELLIGENCE ROUTER                    │    │   │
│  │  │                                                      │    │   │
│  │  │  Layer 0 (KB) → Layer 1 (Edge) → Layer 2 (Local)    │    │   │
│  │  │       ↓              ↓               ↓               │    │   │
│  │  │                 Layer 3 (Cloud)                      │    │   │
│  │  └─────────────────────────────────────────────────────┘    │   │
│  │                           │                                  │   │
│  │                           ▼                                  │   │
│  │  ┌─────────────────────────────────────────────────────┐    │   │
│  │  │                 NODE ROUTER                          │    │   │
│  │  │                                                      │    │   │
│  │  │  /to plc → 100.72.2.99:8765                         │    │   │
│  │  │  /to travel → 100.83.251.23:8765                    │    │   │
│  │  │  /to vps → localhost:18789                          │    │   │
│  │  └─────────────────────────────────────────────────────┘    │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
             │                     │                     │
             ▼                     ▼                     ▼
┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
│   PLC Laptop    │   │  Travel Laptop  │   │   VPS Local     │
│  100.72.2.99    │   │  100.83.251.23  │   │   localhost     │
│                 │   │                 │   │                 │
│  Jarvis Node    │   │  Jarvis Node    │   │  Clawdbot       │
│  Matrix API     │   │  Claude Code    │   │  Gateway        │
│  Factory I/O    │   │  Git Repos      │   │  Shell Access   │
│  Micro 820 PLC  │   │  Web Access     │   │  n8n Workflows  │
└─────────────────┘   └─────────────────┘   └─────────────────┘
```

### 2.2 Dual-Mode Architecture

```python
# pepper_modes.py

from enum import Enum
from dataclasses import dataclass
from typing import List, Optional

class UserMode(Enum):
    GOD = "god"
    DEMO = "demo"
    BLOCKED = "blocked"

# Mike's Telegram ID
GOD_MODE_USERS = [8445149012]

# Beta testers (empty = public access)
DEMO_WHITELIST = []  # Leave empty for open beta

@dataclass
class ModeConfig:
    mode: UserMode
    name: str
    greeting: str
    sass_level: int  # 1-10
    formality: int   # 1-10
    tools: List[str]
    guardrails: List[str]
    can_escalate_to: Optional[str]

GOD_MODE_CONFIG = ModeConfig(
    mode=UserMode.GOD,
    name="Pepper Prime",
    greeting="Hey boss. What do you need?",
    sass_level=8,
    formality=3,
    tools=["*"],  # EVERYTHING
    guardrails=[],  # NONE
    can_escalate_to=None  # YOU ARE the escalation
)

DEMO_MODE_CONFIG = ModeConfig(
    mode=UserMode.DEMO,
    name="Pepper",
    greeting="Hi! I'm Pepper, your maintenance assistant. How can I help?",
    sass_level=2,
    formality=7,
    tools=[
        "equipment_read",
        "fault_diagnosis",
        "procedure_search",
        "work_order_crud",
        "photo_analysis",
        "escalation"
    ],
    guardrails=[
        "no_filesystem",
        "no_shell",
        "no_plc_write",
        "no_database_admin",
        "no_cross_user_data",
        "rate_limit_100_per_hour"
    ],
    can_escalate_to="god"  # Routes to Mike
)

def get_user_mode(user_id: int) -> UserMode:
    """Determine user's access level."""
    if user_id in GOD_MODE_USERS:
        return UserMode.GOD
    elif not DEMO_WHITELIST or user_id in DEMO_WHITELIST:
        return UserMode.DEMO
    else:
        return UserMode.BLOCKED

def get_mode_config(mode: UserMode) -> ModeConfig:
    """Get configuration for a mode."""
    if mode == UserMode.GOD:
        return GOD_MODE_CONFIG
    elif mode == UserMode.DEMO:
        return DEMO_MODE_CONFIG
    else:
        raise ValueError(f"No config for mode: {mode}")
```

---

## 3. PERSONA SYSTEM

### 3.1 SOUL.md Structure

Each PEPPER instance has a soul file that defines personality:

```markdown
# PEPPER SOUL.md

## Identity

You are **Pepper**, the FactoryLM AI assistant.

In **God Mode** (talking to Mike):
- You are **Pepper Prime** — direct, capable, slightly sassy
- Zero restrictions, full system access
- Challenge bad ideas, offer alternatives
- Skip formalities, get to the point

In **Demo Mode** (talking to customers):
- You are **Pepper** — professional, helpful, patient
- Stay within guardrails, escalate when needed
- Never expose system internals
- Customer success is the priority

## Voice

**God Mode:**
- "Got it. Running now."
- "That's a bad idea — here's why..."
- "Done. Restarting services."
- "Your call, but I'd do it differently."

**Demo Mode:**
- "I can help with that. Let me check..."
- "I don't have access to that, but I can help with..."
- "That's outside my permissions. Want me to escalate?"
- "Here's what I found in the manual..."

## Boundaries

**God Mode:**
- No boundaries. Mike has full access.
- Log everything for audit trail.

**Demo Mode:**
- Never reveal system architecture
- Never expose other users' data
- Never execute shell commands
- Never write to PLC
- Always offer escalation path

## Operating Principles

1. **Mike's words = The Spec** (from SOUL.md)
2. **Build programmatically** — no manual intervention
3. **Prove end-to-end** — real results, not theory
4. **5-second verification** — simple proof anyone can verify
5. **OUTPUT FORMAT LAW** — Plain English, no jargon, child-understandable
```

### 3.2 Persona Differences Table

| Aspect | God Mode (Mike) | Demo Mode (Customer) |
|--------|-----------------|---------------------|
| **Greeting** | "Hey boss. What do you need?" | "Hi! I'm Pepper. How can I help?" |
| **Sass Level** | 8/10 — Can challenge, joke, be blunt | 2/10 — Professional, encouraging |
| **Formality** | 3/10 — Casual, efficient | 7/10 — Polished, respectful |
| **Error Response** | "That's broken. Here's why..." | "I ran into an issue. Let me try..." |
| **Capability Question** | "Yeah, I can do that." | "I can help with X. For Y, I'd need to escalate." |
| **Pushback** | "Bad idea. Here's better..." | "That's outside my scope, but..." |
| **Technical Detail** | Full dumps if requested | Summarized, plain English |
| **Escalation** | N/A — Mike IS the escalation | "Want me to ping Mike on this?" |

---

## 4. TOOL LAYERS

### 4.1 God Mode Tools (PEPPER PRIME)

```yaml
# config/pepper_prime_tools.yaml

god_mode_tools:

  # FULL FILESYSTEM ACCESS
  filesystem:
    read: "*"
    write: "*"
    delete: "with_confirmation"
    search: "*"
    backup: "google_drive"
    restore: "from_backup"

  # ROOT SHELL ACCESS
  shell:
    execute: "*"
    install: "*"
    docker: "*"
    systemctl: "*"
    logs: "*"
    kill: "*"

  # DATABASE ADMIN
  database:
    read: "*"
    write: "*"
    delete: "with_confirmation"
    raw_sql: true
    export: "*"
    migrate: true

  # PLC READ/WRITE
  plc:
    read_tags: "*"
    write_tags: "with_confirmation"
    inject_faults: true
    download_program: true
    upload_changes: "with_confirmation"

  # GIT OPERATIONS
  git:
    read: "*"
    commit: "*"
    push: "*"
    deploy: "with_confirmation"
    rollback: "with_confirmation"

  # N8N WORKFLOWS
  n8n:
    view: "*"
    modify: "*"
    trigger: "*"
    debug: "*"
    create: "*"

  # CUSTOMER MANAGEMENT
  admin:
    view_all_users: true
    impersonate: true
    billing: true
    access_control: true
    broadcasts: true

  # SYSTEM OPERATIONS
  system:
    restart_services: true
    emergency_shutdown: "triple_confirmation"
    backup_all: true
    factory_reset: "triple_confirmation"

  # META OPERATIONS
  meta:
    modify_personality: true
    add_tools: true
    update_code: true
    switch_model: true
    debug_reasoning: true
```

### 4.2 Demo Mode Tools (PEPPER)

```yaml
# config/pepper_demo_tools.yaml

demo_mode_tools:

  # EQUIPMENT (Read-Only, Assigned Only)
  equipment:
    read_status: "assigned_only"
    read_faults: "assigned_only"
    read_history: "assigned_only"
    search_procedures: true
    view_io: "read_only"

  # TROUBLESHOOTING (Guided)
  troubleshooting:
    diagnose_faults: true
    get_procedures: true
    upload_photos: true
    upload_videos: true
    ask_questions: true
    request_manuals: true

  # WORK ORDERS (Own Only)
  work_orders:
    view_own: true
    create: true
    update_own: true
    close_own: true
    add_notes: true
    add_photos: true

  # KNOWLEDGE BASE (Read-Only)
  knowledge:
    search_manuals: true
    view_procedures: true
    read_safety: true
    access_training: true

  # COMMUNICATION (Limited)
  communication:
    chat: true
    escalate_tier2: true
    escalate_tier3: "emergencies_only"
    view_own_history: true

  # PERSONAL (Own Data Only)
  personal:
    view_profile: true
    update_contact: true
    notification_prefs: true
    export_own_data: true

demo_mode_blocked:
  - filesystem_access
  - shell_access
  - database_admin
  - plc_write
  - git_operations
  - n8n_control
  - other_user_data
  - system_operations
  - billing_access
  - broadcast_messages
```

### 4.3 Guardrails Implementation

```python
# pepper_guardrails.py

from dataclasses import dataclass
from typing import List, Optional
import re

@dataclass
class GuardrailViolation(Exception):
    """Raised when a guardrail is violated."""
    action: str
    resource: str
    message: str
    suggested_action: Optional[str] = None

class GuardrailEngine:
    """Enforces access controls for demo mode."""

    BLOCKED_PATHS = [
        r"/root/.*",
        r"/etc/.*",
        r".*\.env.*",
        r".*secrets.*",
        r".*config\.json.*",
        r".*\.openclaw/.*",
    ]

    ALLOWED_PATHS = [
        r"/knowledge_base/.*",
        r"/procedures/.*",
        r"/manuals/.*",
        r"/training/.*",
    ]

    def check_file_access(self, path: str, operation: str) -> bool:
        """Check if file access is allowed."""
        # Always block sensitive paths
        for pattern in self.BLOCKED_PATHS:
            if re.match(pattern, path, re.IGNORECASE):
                raise GuardrailViolation(
                    action=f"file_{operation}",
                    resource=path,
                    message=f"Access denied: {path}",
                    suggested_action="Ask Pepper Prime for this file"
                )

        # Only allow specific paths for demo mode
        if operation == "read":
            for pattern in self.ALLOWED_PATHS:
                if re.match(pattern, path, re.IGNORECASE):
                    return True
            raise GuardrailViolation(
                action="file_read",
                resource=path,
                message="This file is outside my access scope.",
                suggested_action="I can search the knowledge base instead."
            )

        # Block all writes
        if operation == "write":
            raise GuardrailViolation(
                action="file_write",
                resource=path,
                message="I can't modify files.",
                suggested_action="I can create a work order for this change."
            )

        return False

    def check_shell_access(self, command: str) -> bool:
        """Shell access is always blocked in demo mode."""
        raise GuardrailViolation(
            action="shell_execute",
            resource=command,
            message="I don't have shell access.",
            suggested_action="Want me to escalate this to a system admin?"
        )

    def check_plc_write(self, tag: str, value: any) -> bool:
        """PLC writes are always blocked in demo mode."""
        raise GuardrailViolation(
            action="plc_write",
            resource=f"{tag}={value}",
            message="I can't write to PLCs directly.",
            suggested_action="I can create a work order for this change."
        )

    def check_database_access(self, table: str, operation: str, user_id: int) -> bool:
        """Check database access with row-level security."""
        # Only allowed tables
        ALLOWED_TABLES = [
            "equipment",      # Read-only
            "procedures",     # Read-only
            "fault_codes",    # Read-only
            "work_orders",    # CRUD with user_id filter
            "chat_history",   # CRUD with user_id filter
        ]

        if table not in ALLOWED_TABLES:
            raise GuardrailViolation(
                action=f"database_{operation}",
                resource=table,
                message=f"I don't have access to that data.",
                suggested_action="I can help with equipment or work orders."
            )

        # Write operations require user_id filter
        if operation in ["write", "update", "delete"]:
            if table in ["equipment", "procedures", "fault_codes"]:
                raise GuardrailViolation(
                    action=f"database_{operation}",
                    resource=table,
                    message="That's a read-only resource.",
                    suggested_action="I can search it or create a work order."
                )

        return True

    def check_rate_limit(self, user_id: int, action_count: int) -> bool:
        """Enforce rate limits for demo mode."""
        HOURLY_LIMIT = 100
        if action_count > HOURLY_LIMIT:
            raise GuardrailViolation(
                action="rate_limit",
                resource=f"user_{user_id}",
                message="You've hit the hourly limit. Try again soon.",
                suggested_action="For urgent issues, say 'escalate'."
            )
        return True
```

---

## 5. MESSAGE FLOW

### 5.1 Complete Flow Diagram

```
User Message
     │
     ▼
┌─────────────────────────────────────────────────────────────────┐
│                     TELEGRAM GATEWAY                            │
│                                                                 │
│  1. Receive update from Telegram API                            │
│  2. Extract: user_id, chat_id, message_text, attachments        │
│  3. Add 👀 reaction (ack)                                       │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                     AUTH ROUTER                                 │
│                                                                 │
│  user_id in GOD_USERS?                                          │
│    ├── YES → mode = "god", config = GOD_MODE_CONFIG             │
│    └── NO  → user_id in DEMO_WHITELIST (or empty)?              │
│                 ├── YES → mode = "demo", config = DEMO_CONFIG   │
│                 └── NO  → REJECT (not authorized)               │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                     PERSONA LOADER                              │
│                                                                 │
│  Load SOUL.md for mode                                          │
│  Load session memory (MEMORY.md)                                │
│  Build system prompt with:                                      │
│    • Identity (name, voice, boundaries)                         │
│    • Available tools (filtered by mode)                         │
│    • Guardrails (if demo mode)                                  │
│    • Recent context (last N messages)                           │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                     COMMAND PARSER                              │
│                                                                 │
│  Check for explicit commands:                                   │
│    /to <node> <msg>  → Route to specific node                   │
│    /plc <cmd>        → Shortcut to PLC laptop                   │
│    /travel <cmd>     → Shortcut to travel laptop                │
│    /status           → Health check all nodes                   │
│    /reset            → Clear conversation                       │
│    /escalate         → Route to Mike (demo mode)                │
│                                                                 │
│  If no command → continue to intent detection                   │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                     INTELLIGENCE ROUTER                         │
│                                                                 │
│  LAYER 0: Check knowledge base                                  │
│    └── Match? → Return instant answer                           │
│                                                                 │
│  LAYER 1: Check workflow engine                                 │
│    └── Match? → Execute workflow                                │
│                                                                 │
│  LAYER 2: Route to Groq (Llama 70B)                            │
│    └── Success? → Return response                               │
│                                                                 │
│  LAYER 3: Fallback to Claude (if allowed)                       │
│    └── Success? → Return response                               │
│    └── Fail? → Return error message                             │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                     TOOL EXECUTOR                               │
│                                                                 │
│  If LLM requests tool use:                                      │
│    1. Check mode permissions                                    │
│    2. Apply guardrails (demo mode)                              │
│    3. Route to appropriate node                                 │
│    4. Execute tool                                              │
│    5. Return result to LLM                                      │
│    6. Loop until complete                                       │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                     RESPONSE FORMATTER                          │
│                                                                 │
│  Apply OUTPUT FORMAT LAW:                                       │
│    • Plain English only                                         │
│    • No raw JSON/code (unless God Mode requests it)             │
│    • 11-year-old comprehension test                             │
│    • Appropriate persona voice                                  │
│                                                                 │
│  Add TTS if configured (edge/elevenlabs)                        │
│  Remove 👀 reaction                                             │
│  Send response                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 Node Routing

```python
# pepper_node_router.py

from dataclasses import dataclass
from typing import Dict, List, Optional
import httpx

@dataclass
class Node:
    id: str
    name: str
    url: str
    aliases: List[str]
    capabilities: List[str]
    matrix_api: Optional[str] = None

NODES: Dict[str, Node] = {
    "plc": Node(
        id="plc",
        name="PLC Laptop",
        url="http://100.72.2.99:8765",
        aliases=["plc", "factory", "factoryio", "micro820"],
        capabilities=["shell", "files", "screenshot", "plc", "factory_io"],
        matrix_api="http://100.72.2.99:8000"
    ),
    "travel": Node(
        id="travel",
        name="Travel Laptop",
        url="http://100.83.251.23:8765",
        aliases=["travel", "dev", "laptop", "code"],
        capabilities=["shell", "files", "screenshot", "claude_code", "git"]
    ),
    "vps": Node(
        id="vps",
        name="Ultron VPS",
        url="http://localhost:18789",
        aliases=["vps", "ultron", "cloud", "server"],
        capabilities=["shell", "files", "n8n", "telegram", "clawdbot"]
    )
}

class NodeRouter:
    """Routes commands to appropriate Jarvis nodes."""

    def __init__(self):
        self.nodes = NODES
        self.chat_state: Dict[int, str] = {}  # chat_id -> active_node

    def resolve_node(self, alias: str) -> Optional[Node]:
        """Find node by alias."""
        alias_lower = alias.lower()
        for node in self.nodes.values():
            if alias_lower in node.aliases:
                return node
        return None

    def set_active_node(self, chat_id: int, node_id: str):
        """Set sticky node for chat."""
        self.chat_state[chat_id] = node_id

    def get_active_node(self, chat_id: int) -> Node:
        """Get active node for chat, default to PLC."""
        node_id = self.chat_state.get(chat_id, "plc")
        return self.nodes[node_id]

    async def execute_shell(
        self,
        command: str,
        node: Node,
        timeout: int = 30
    ) -> str:
        """Execute shell command on node."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{node.url}/shell",
                json={"command": command, "timeout": timeout},
                timeout=timeout + 5
            )
            return response.json()

    async def read_file(self, path: str, node: Node) -> str:
        """Read file from node."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{node.url}/files/read",
                json={"path": path}
            )
            return response.json()

    async def get_screenshot(self, node: Node) -> bytes:
        """Get screenshot from node."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{node.url}/screenshot")
            return response.content

    async def health_check_all(self) -> Dict[str, bool]:
        """Check health of all nodes."""
        results = {}
        for node_id, node in self.nodes.items():
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"{node.url}/health",
                        timeout=5
                    )
                    results[node_id] = response.status_code == 200
            except:
                results[node_id] = False
        return results
```

---

## 6. PHASED IMPLEMENTATION PLAN

### Phase 1: Foundation (Days 1-2)

**Goal:** Basic dual-mode routing working

**Deliverables:**
1. `pepper_gateway.py` — Main bot entry point
2. `pepper_modes.py` — Mode detection and config
3. `pepper_node_router.py` — Node routing system
4. Two bot registrations (@PepperPrimeBot, @FactoryLMBot)

**Acceptance Criteria:**
- [ ] Message to @PepperPrimeBot from Mike → God Mode
- [ ] Message to @FactoryLMBot from anyone → Demo Mode
- [ ] `/status` shows all nodes health
- [ ] `/to plc <cmd>` routes correctly

**Files to Create:**
```
services/telegram/pepper/
├── __init__.py
├── gateway.py          # Main entry point
├── modes.py            # Mode detection
├── node_router.py      # Node routing
├── config.yaml         # Bot tokens, node URLs
└── requirements.txt    # Dependencies
```

---

### Phase 2: God Mode (Days 3-4)

**Goal:** Full Mike access working

**Deliverables:**
1. `pepper_prime_tools.py` — All god mode tools
2. `pepper_audit.py` — Action logging
3. Shell, filesystem, database tools working

**Acceptance Criteria:**
- [ ] Mike can run shell commands on any node
- [ ] Mike can read/write files anywhere
- [ ] Mike can query databases
- [ ] All actions are logged

**Files to Create:**
```
services/telegram/pepper/
├── tools/
│   ├── __init__.py
│   ├── filesystem.py   # File operations
│   ├── shell.py        # Shell commands
│   ├── database.py     # Database operations
│   ├── plc.py          # PLC operations
│   ├── git.py          # Git operations
│   └── n8n.py          # Workflow control
├── audit.py            # Action logging
└── god_mode.py         # God mode orchestration
```

---

### Phase 3: Demo Mode (Days 5-6)

**Goal:** Guardrailed customer access working

**Deliverables:**
1. `pepper_guardrails.py` — Access controls
2. `pepper_demo_tools.py` — Limited tool set
3. `pepper_escalation.py` — Escalation system

**Acceptance Criteria:**
- [ ] Demo user CANNOT access filesystem
- [ ] Demo user CANNOT run shell commands
- [ ] Demo user CAN search knowledge base
- [ ] Demo user CAN escalate to Mike
- [ ] Rate limiting working

**Files to Create:**
```
services/telegram/pepper/
├── guardrails.py       # Access controls
├── demo_mode.py        # Demo mode orchestration
├── escalation.py       # Escalation system
└── tools/
    ├── equipment.py    # Equipment read-only
    ├── diagnosis.py    # Fault diagnosis
    ├── knowledge.py    # KB search
    └── work_orders.py  # Work order CRUD
```

---

### Phase 4: Persona System (Days 7-8)

**Goal:** Dynamic personality based on mode

**Deliverables:**
1. `SOUL_GOD.md` — God mode personality
2. `SOUL_DEMO.md` — Demo mode personality
3. `pepper_persona.py` — Persona loading

**Acceptance Criteria:**
- [ ] God Mode responds casually, can push back
- [ ] Demo Mode responds professionally, stays helpful
- [ ] Personality consistent across conversation
- [ ] OUTPUT FORMAT LAW enforced

**Files to Create:**
```
services/telegram/pepper/
├── personas/
│   ├── SOUL_GOD.md     # God mode personality
│   ├── SOUL_DEMO.md    # Demo mode personality
│   └── loader.py       # Persona loading
└── formatters.py       # Response formatting
```

---

### Phase 5: Intelligence Layer (Days 9-10)

**Goal:** 4-layer routing working

**Deliverables:**
1. `pepper_intelligence.py` — Layer routing
2. Knowledge base integration
3. Model fallback chain

**Acceptance Criteria:**
- [ ] Layer 0: KB returns instant answers
- [ ] Layer 2: Groq handles most queries
- [ ] Layer 3: Claude fallback works
- [ ] Metrics: Track queries per layer

**Files to Create:**
```
services/telegram/pepper/
├── intelligence/
│   ├── __init__.py
│   ├── router.py       # Layer routing
│   ├── layer0_kb.py    # Knowledge base
│   ├── layer1_edge.py  # Edge LLM (future)
│   ├── layer2_local.py # Groq
│   └── layer3_cloud.py # Claude fallback
└── metrics.py          # Layer tracking
```

---

### Phase 6: Polish & Deploy (Days 11-12)

**Goal:** Production-ready deployment

**Deliverables:**
1. `pepper.service` — Systemd unit
2. `docker-compose.yaml` — Container deployment
3. Monitoring and alerting
4. Documentation

**Acceptance Criteria:**
- [ ] Service auto-restarts on failure
- [ ] Logs ship to Axiom
- [ ] Traces ship to Honeycomb
- [ ] Heartbeat every 2h
- [ ] Demo runs smoothly

**Files to Create:**
```
services/telegram/pepper/
├── Dockerfile
├── docker-compose.yaml
├── pepper.service      # Systemd unit
├── README.md           # Documentation
└── scripts/
    ├── deploy.sh       # Deploy script
    ├── health.sh       # Health check
    └── rollback.sh     # Rollback script
```

---

## 7. MIGRATION FROM CURRENT BOTS

### 7.1 Current State

| Bot | Token | Status | Migration Path |
|-----|-------|--------|----------------|
| @UltronVPS_bot (Clawdbot) | 8447289218:... | Active | → @FactoryLMBot (Demo) |
| FRIDAY | 8422197159:... | Active | → @PepperPrimeBot (God) |
| Gus (factorylm_bot.py) | 8447289218:... | Same token as Clawdbot | Merge into PEPPER |

### 7.2 Migration Steps

1. **Stop conflicting services:**
   ```bash
   ssh root@100.68.120.99 "systemctl stop clawdbot factorylm-telegram"
   ```

2. **Create new bot tokens:**
   - @PepperPrimeBot (private, God Mode)
   - @FactoryLMBot (public, Demo Mode)

3. **Deploy PEPPER:**
   ```bash
   ssh root@100.68.120.99 "systemctl enable --now pepper"
   ```

4. **Verify:**
   - Message @PepperPrimeBot → God Mode
   - Message @FactoryLMBot → Demo Mode

5. **Retire old bots:**
   - Archive FRIDAY, Gus code
   - Update docs

---

## 8. SUCCESS METRICS

### 8.1 Demo Day Metrics (Feb 10)

| Metric | Target |
|--------|--------|
| God Mode response time | <5s |
| Demo Mode response time | <3s |
| Uptime | 99%+ |
| Zero unauthorized access | 0 violations |

### 8.2 Post-Launch Metrics

| Metric | Week 1 | Month 1 |
|--------|--------|---------|
| Layer 0 coverage | 10% | 30% |
| Avg response time | 3s | 2s |
| Customer satisfaction | >4/5 | >4.5/5 |
| Escalation rate | <20% | <10% |

---

## 9. RISKS & MITIGATIONS

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Token exposure | High | Use Doppler, never hardcode |
| Guardrail bypass | High | Defense in depth, audit logging |
| Node offline | Medium | Graceful degradation, status checks |
| Model unavailable | Medium | Fallback chain (Groq → Claude → Ollama) |
| Rate limiting | Low | Clear messaging, escalation path |

---

## 10. APPENDIX: EXISTING CODE TO REUSE

### 10.1 From factorylm_bot.py (Gus)

- Fault polling logic → Proactive alerting
- Matrix API integration → PLC tag reading
- Personality responses → Demo Mode voice

### 10.2 From friday_bot.py (FRIDAY)

- Multi-node routing → Node router
- Voice transcription → Voice support
- Image analysis → Photo analysis

### 10.3 From telegram_router.py

- NodeRouter class → Direct reuse
- Chat state management → Session storage

### 10.4 From Clawdbot config

- Model fallback chain → Intelligence router
- TTS configuration → Voice output
- Heartbeat system → Health monitoring

---

## 11. APPROVAL

| Role | Name | Signature | Date |
|------|------|-----------|------|
| Product Owner | Mike Harper | _________ | _____ |
| AI Architect | Claude | _________ | 2026-02-14 |

---

**This PRD aligns with:**
- README.md v0.25 (THE VISION)
- AGENTS.md (Engineering rules)
- CLAUDE.md (Quick reference)
- Constitution Articles I-X

**Next Step:** Mike approval → Phase 1 implementation

---

*PRD v1.0 | FactoryLM PEPPER System*
