# PEPPER Tools System

Comprehensive toolset with God Mode and Demo Mode access control for FactoryLM's dual-mode Telegram bot.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    PEPPER Tools                         │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────────┐         ┌──────────────┐            │
│  │  God Mode    │         │  Demo Mode   │            │
│  │  (Mike)      │         │  (Customers) │            │
│  └──────┬───────┘         └──────┬───────┘            │
│         │                        │                     │
│         ▼                        ▼                     │
│  ┌─────────────────────────────────────┐               │
│  │        Tool Registry                │               │
│  └─────────────────────────────────────┘               │
│         │                                               │
│         ├─── Filesystem (God only)                     │
│         ├─── Shell (God only)                          │
│         ├─── Equipment (Both, read-only)               │
│         ├─── Diagnosis (Both)                          │
│         ├─── Work Orders (Demo: own only)              │
│         └─── Escalation (Demo only)                    │
│                                                         │
│  ┌─────────────────────────────────────┐               │
│  │     Guardrail Engine                │               │
│  │  - File access control              │               │
│  │  - Command filtering                │               │
│  │  - PLC write protection             │               │
│  │  - Database access control          │               │
│  │  - Rate limiting                    │               │
│  └─────────────────────────────────────┘               │
└─────────────────────────────────────────────────────────┘
```

## Tools Overview

### 1. Filesystem Tool (God Mode Only)

**Purpose:** File operations with full system access.

**Operations:**
- `read`: Read file contents
- `write`: Write content to file (creates backup)
- `search`: Glob pattern file search
- `list`: List directory contents

**Example:**
```python
await tool.execute_with_checks(
    params={
        "operation": "read",
        "path": "/knowledge_base/procedures/conveyor_maintenance.md"
    },
    context=god_mode_context
)
```

### 2. Shell Tool (God Mode Only)

**Purpose:** Execute shell commands and scripts on local or remote nodes.

**Operations:**
- `execute`: Run shell command
- `run_script`: Execute script file (.py, .sh, .ps1, .bat)

**Nodes:**
- `plc_laptop`: http://100.72.2.99:8765
- `travel_laptop`: http://100.83.251.23:8765
- `vps`: http://100.68.120.99:8765
- `local`: Current machine

**Example:**
```python
await tool.execute_with_checks(
    params={
        "operation": "execute",
        "command": "python get_plc_status.py",
        "node": "plc_laptop",
        "timeout": 30
    },
    context=god_mode_context
)
```

### 3. Equipment Tool (Both Modes, Read-Only)

**Purpose:** Equipment status, diagnostics, and procedure search.

**Operations:**
- `get_status`: Get equipment status from Matrix API
- `get_faults`: Get active faults
- `get_io_panel`: Current I/O state
- `search_procedures`: Search knowledge base
- `get_maintenance_history`: Maintenance records

**Example:**
```python
await tool.execute_with_checks(
    params={
        "operation": "get_status",
        "equipment_id": "conveyor_01"
    },
    context=demo_mode_context
)
```

### 4. Diagnosis Tool (Both Modes)

**Purpose:** AI-powered fault diagnosis using Groq/Claude.

**Operations:**
- `diagnose`: Natural language diagnosis
- `get_fault_history`: Historical fault data
- `suggest_solution`: Step-by-step troubleshooting

**Example:**
```python
await tool.execute_with_checks(
    params={
        "operation": "diagnose",
        "question": "Why is the conveyor belt running slowly?",
        "equipment_id": "conveyor_01",
        "context": {"current_speed": 45, "target_speed": 60},
        "use_claude": False  # Use Groq by default
    },
    context=demo_mode_context
)
```

### 5. Work Orders Tool (Demo: Own Only)

**Purpose:** Create, update, and manage work orders.

**Operations:**
- `create`: Create new work order
- `update`: Update work order (status, notes)
- `list_my_work_orders`: List user's work orders
- `close`: Close work order
- `get_details`: Get work order details

**Guardrails:**
- Demo users can only access their own work orders
- God mode has access to all work orders

**Example:**
```python
await tool.execute_with_checks(
    params={
        "operation": "create",
        "description": "Conveyor belt running at 75% speed",
        "equipment_id": "conveyor_01",
        "priority": "high"
    },
    context=demo_mode_context
)
```

### 6. Escalation Tool (Demo Mode Only)

**Purpose:** Escalate issues to Mike (Tier 3 support).

**Operations:**
- `escalate_to_mike`: Send notification to Mike
- `request_callback`: Request phone callback

**Example:**
```python
await tool.execute_with_checks(
    params={
        "operation": "escalate_to_mike",
        "reason": "Equipment fault requires immediate attention",
        "urgency": "high",
        "context": {
            "equipment_id": "conveyor_01",
            "fault_code": "E1001"
        }
    },
    context=demo_mode_context
)
```

## Guardrails System

### File Access Control

**Blocked Paths:**
- `/root/`, `/etc/`, `/var/`, `/home/`
- `*.env*`, `*secrets*`, `*password*`, `*key*`
- System directories (`C:/Windows/`, `/sys/`, `/proc/`)

**Allowed Paths:**
- `/knowledge_base/`, `/procedures/`, `/manuals/`
- `/documentation/`, `/work_orders/`, `/equipment/`

### Shell Command Filtering

**Blocked Commands:**
- Destructive: `rm`, `del`, `format`, `shutdown`, `reboot`, `kill`
- Privilege escalation: `sudo`, `chmod`, `chown`
- Dangerous: `dd`, `mkfs`, `>`, `>>`

**Allowed Commands:**
- Read-only: `ls`, `dir`, `cat`, `type`, `grep`, `find`, `pwd`

### PLC Write Protection

**Protected Tags:**
- `ESTOP`, `SAFETY`, `INTERLOCK`, `EMERGENCY`, `SHUTDOWN`
- Any boolean writes to control tags (STOP, ENABLE, DISABLE, ACTIVE)

### Rate Limiting

- **Per Minute:** 10 actions
- **Per Hour:** 100 actions

## Usage Examples

### Initialize Registry

```python
from pepper.tools import get_tool_registry, ToolContext, UserMode

# Get registry with API keys
registry = get_tool_registry(
    groq_api_key=os.getenv("GROQ_API_KEY"),
    claude_api_key=os.getenv("CLAUDE_API_KEY")
)
```

### Execute Tool (God Mode)

```python
# Create context
context = ToolContext(
    user_id=1,  # Mike
    chat_id=123456,
    mode=UserMode.GOD,
    active_twin="factory_floor",
    session_data={}
)

# Get tool
tool = registry.get("filesystem")

# Execute
result = await tool.execute_with_checks(
    params={
        "operation": "read",
        "path": "/etc/factorylm/config.json"
    },
    context=context
)

if result.is_success:
    print(result.data["content"])
else:
    print(f"Error: {result.error}")
```

### Execute Tool (Demo Mode)

```python
# Create context
context = ToolContext(
    user_id=42,  # Demo user
    chat_id=789012,
    mode=UserMode.DEMO,
    active_twin="conveyor_01",
    session_data={},
    username="demo_user"
)

# Get tool
tool = registry.get("equipment")

# Execute
result = await tool.execute_with_checks(
    params={
        "operation": "get_status",
        "equipment_id": "conveyor_01"
    },
    context=context
)

if result.is_success:
    status = result.data
    print(f"Equipment: {status['equipment_id']}")
    print(f"Status: {status['status']}")
    print(f"State: {status['state']}")
elif result.is_blocked:
    print(f"Blocked: {result.error}")
    print(f"Suggestion: {result.suggested_action}")
```

### Handle Guardrail Violations

```python
# Demo user tries to use filesystem tool
tool = registry.get("filesystem")
result = await tool.execute_with_checks(
    params={"operation": "read", "path": "/etc/passwd"},
    context=demo_mode_context
)

if result.is_blocked:
    print(f"❌ {result.error}")
    print(f"💡 {result.suggested_action}")
    # Output:
    # ❌ Tool 'filesystem' requires god mode
    # 💡 This action requires elevated permissions. Contact Mike if you need this capability.
```

## Tool Availability Matrix

| Tool | God Mode | Demo Mode | Notes |
|------|----------|-----------|-------|
| filesystem | ✅ Full | ❌ Blocked | System file access |
| shell | ✅ Full | ❌ Blocked | Command execution |
| equipment | ✅ Full | ✅ Read-only | Equipment status |
| diagnosis | ✅ Full | ✅ Full | AI diagnosis |
| work_orders | ✅ All records | ✅ Own only | Work order CRUD |
| escalation | ❌ Not needed | ✅ Full | Contact Mike |

## Integration with PEPPER

### In Bot Handler

```python
from pepper.tools import get_tool_registry, ToolContext, UserMode

class PepperBot:
    def __init__(self):
        self.registry = get_tool_registry(
            groq_api_key=config.GROQ_API_KEY,
            claude_api_key=config.CLAUDE_API_KEY
        )

    async def handle_tool_request(self, message, user_mode):
        # Create context
        context = ToolContext(
            user_id=message.from_user.id,
            chat_id=message.chat.id,
            mode=user_mode,
            active_twin=self.get_active_twin(message),
            session_data=self.get_session(message),
            username=message.from_user.username
        )

        # Parse tool request
        tool_name, params = self.parse_tool_request(message.text)

        # Get and execute tool
        tool = self.registry.get(tool_name)
        if not tool:
            return f"Unknown tool: {tool_name}"

        result = await tool.execute_with_checks(params, context)

        # Format response
        return self.format_tool_result(result)
```

## Error Handling

All tools return `ToolResult` with consistent structure:

```python
@dataclass
class ToolResult:
    status: ToolResultStatus  # SUCCESS, ERROR, BLOCKED, TIMEOUT
    data: Any = None
    error: Optional[str] = None
    suggested_action: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
```

**Status Types:**
- `SUCCESS`: Operation completed successfully
- `ERROR`: Operation failed (technical error)
- `BLOCKED`: Operation blocked by guardrails (permission denied)
- `TIMEOUT`: Operation timed out

## Testing

### Unit Tests

```python
import pytest
from pepper.tools import get_tool_registry, ToolContext, UserMode

@pytest.mark.asyncio
async def test_filesystem_god_mode():
    registry = get_tool_registry()
    tool = registry.get("filesystem")

    context = ToolContext(
        user_id=1,
        chat_id=123,
        mode=UserMode.GOD,
        active_twin="test",
        session_data={}
    )

    result = await tool.execute_with_checks(
        params={"operation": "list", "path": "."},
        context=context
    )

    assert result.is_success

@pytest.mark.asyncio
async def test_filesystem_demo_blocked():
    registry = get_tool_registry()
    tool = registry.get("filesystem")

    context = ToolContext(
        user_id=42,
        chat_id=456,
        mode=UserMode.DEMO,
        active_twin="test",
        session_data={}
    )

    result = await tool.execute_with_checks(
        params={"operation": "read", "path": "/etc/passwd"},
        context=context
    )

    assert result.is_blocked
    assert "requires god mode" in result.error.lower()
```

## Security Considerations

1. **Path Traversal:** All file paths are normalized and validated
2. **Command Injection:** Shell commands are filtered for dangerous operations
3. **PLC Safety:** Critical safety tags are protected from modification
4. **Rate Limiting:** Prevents abuse and DoS attacks
5. **Ownership Validation:** Demo users can only access their own resources
6. **Audit Logging:** All tool executions are logged for security review

## Future Enhancements

1. **Tool Chaining:** Execute multiple tools in sequence
2. **Advanced Guardrails:** ML-based anomaly detection
3. **Context-Aware Permissions:** Dynamic permission adjustment based on situation
4. **Tool History:** Track tool execution history per user
5. **Custom Tool Plugins:** Allow extending with custom tools
6. **Workflow Automation:** Create tool execution workflows

## Version History

- **v1.0.0** (2024-02-14): Initial implementation
  - 6 core tools (filesystem, shell, equipment, diagnosis, work_orders, escalation)
  - Guardrail engine with comprehensive security controls
  - God Mode and Demo Mode access control
  - Rate limiting and ownership validation
