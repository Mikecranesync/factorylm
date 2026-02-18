# PEPPER Tools - Quick Start Guide

Get up and running with the PEPPER Tools System in 5 minutes.

## Installation

```bash
# Navigate to project directory
cd /path/to/FactoryLM

# Install dependencies (if needed)
pip install httpx asyncio

# No additional dependencies required - uses Python standard library
```

## Basic Usage

### 1. Initialize Tool Registry

```python
from pepper.tools import get_tool_registry, ToolContext, UserMode

# Create registry with API keys
registry = get_tool_registry(
    groq_api_key="your_groq_api_key",
    claude_api_key="your_claude_api_key"  # Optional
)
```

### 2. Create Tool Context

```python
# For God Mode (Mike)
god_context = ToolContext(
    user_id=1,           # Mike's user ID
    chat_id=123456,
    mode=UserMode.GOD,
    active_twin="factory",
    session_data={}
)

# For Demo Mode (Customer)
demo_context = ToolContext(
    user_id=42,
    chat_id=789012,
    mode=UserMode.DEMO,
    active_twin="conveyor_01",
    session_data={},
    username="demo_user"
)
```

### 3. Execute a Tool

```python
# Get equipment status
tool = registry.get("equipment")
result = await tool.execute_with_checks(
    params={
        "operation": "get_status",
        "equipment_id": "conveyor_01"
    },
    context=demo_context
)

# Check result
if result.is_success:
    print(f"Status: {result.data['status']}")
    print(f"State: {result.data['state']}")
elif result.is_blocked:
    print(f"Blocked: {result.error}")
    print(f"Suggestion: {result.suggested_action}")
else:
    print(f"Error: {result.error}")
```

## Common Examples

### Check Equipment Status

```python
tool = registry.get("equipment")
result = await tool.execute_with_checks(
    params={
        "operation": "get_status",
        "equipment_id": "conveyor_01"
    },
    context=context
)
```

### Run AI Diagnosis

```python
tool = registry.get("diagnosis")
result = await tool.execute_with_checks(
    params={
        "operation": "diagnose",
        "question": "Why is the conveyor running slowly?",
        "equipment_id": "conveyor_01"
    },
    context=context
)
```

### Create Work Order

```python
tool = registry.get("work_orders")
result = await tool.execute_with_checks(
    params={
        "operation": "create",
        "description": "Conveyor belt needs maintenance",
        "equipment_id": "conveyor_01",
        "priority": "high"
    },
    context=context
)
```

### Execute Shell Command (God Mode Only)

```python
tool = registry.get("shell")
result = await tool.execute_with_checks(
    params={
        "operation": "execute",
        "command": "ls -la",
        "node": "local",
        "timeout": 30
    },
    context=god_context  # Must be God Mode
)
```

### Escalate to Mike (Demo Mode)

```python
tool = registry.get("escalation")
result = await tool.execute_with_checks(
    params={
        "operation": "escalate_to_mike",
        "reason": "Equipment fault requires immediate attention",
        "urgency": "high"
    },
    context=demo_context
)
```

## Testing

### Run Test Suite

```bash
cd services/telegram/pepper/tools
python test_tools.py
```

Expected output:
```
============================================================
PEPPER Tools System - Test Suite
============================================================

============================================================
Testing Tool Registry Initialization
============================================================

✓ Registered tools: filesystem, shell, equipment, diagnosis, work_orders, escalation
  Total: 6 tools

✓ All tools registered successfully

[... more tests ...]

============================================================
✓ ALL TESTS PASSED
============================================================

Tool system is ready for integration with PEPPER!
```

### Run Example Integration

```bash
python example_integration.py
```

## Integration with Bot

### Minimal Bot Example

```python
from pepper.tools import get_tool_registry, ToolContext, UserMode

class MinimalBot:
    def __init__(self):
        self.registry = get_tool_registry(
            groq_api_key="your_key"
        )

    async def handle_message(self, user_id, chat_id, message):
        # Determine user mode
        mode = UserMode.GOD if user_id == 1 else UserMode.DEMO

        # Create context
        context = ToolContext(
            user_id=user_id,
            chat_id=chat_id,
            mode=mode,
            active_twin="factory",
            session_data={}
        )

        # Route to appropriate tool
        if "status" in message.lower():
            tool = self.registry.get("equipment")
            result = await tool.execute_with_checks(
                params={
                    "operation": "get_status",
                    "equipment_id": "conveyor_01"
                },
                context=context
            )
            return self.format_result(result)

    def format_result(self, result):
        if result.is_success:
            return str(result.data)
        else:
            return f"Error: {result.error}"
```

## Available Tools

| Tool | Command | God | Demo |
|------|---------|-----|------|
| **equipment** | `get_status`, `get_faults`, `get_io_panel` | ✅ | ✅ |
| **diagnosis** | `diagnose`, `suggest_solution` | ✅ | ✅ |
| **work_orders** | `create`, `update`, `list_my_work_orders` | ✅ | ✅* |
| **escalation** | `escalate_to_mike`, `request_callback` | ❌ | ✅ |
| **filesystem** | `read`, `write`, `search`, `list` | ✅ | ❌ |
| **shell** | `execute`, `run_script` | ✅ | ❌ |

\* Demo users can only access their own work orders

## Guardrails

### Blocked Paths (Demo Mode)
```
/root/
/etc/
/var/
*.env*
*secrets*
*password*
```

### Allowed Paths (Demo Mode)
```
/knowledge_base/
/procedures/
/manuals/
/documentation/
```

### Blocked Commands (Demo Mode)
```
rm, del, format, shutdown, reboot
sudo, chmod, chown
dd, mkfs
>, >>
```

### Rate Limits
- **Per Minute:** 10 actions
- **Per Hour:** 100 actions

## Troubleshooting

### "Tool requires god mode"
**Solution:** This tool is restricted to God Mode. Use a different tool or escalate to Mike.

### "Access to path is restricted"
**Solution:** Demo mode can only access allowed directories. Contact Mike if you need system file access.

### "Rate limit exceeded"
**Solution:** Wait a moment before trying again. Demo mode has limits to prevent abuse.

### "Cannot modify work order"
**Solution:** Demo users can only modify their own work orders. This work order belongs to someone else.

## Configuration

### API Keys

Set environment variables:
```bash
export GROQ_API_KEY="your_groq_key"
export CLAUDE_API_KEY="your_claude_key"  # Optional
```

Or pass directly:
```python
registry = get_tool_registry(
    groq_api_key=os.getenv("GROQ_API_KEY"),
    claude_api_key=os.getenv("CLAUDE_API_KEY")
)
```

### Node Endpoints

Edit `shell.py` to configure remote nodes:
```python
NODES = {
    "plc_laptop": "http://100.72.2.99:8765",
    "travel_laptop": "http://100.83.251.23:8765",
    "vps": "http://100.68.120.99:8765",
    "local": "local"
}
```

### Matrix API

Edit `equipment.py` to configure Matrix API:
```python
MATRIX_API_URL = "http://100.68.120.99:8080/api/v1"
```

## Best Practices

1. **Always check result status** before using data
2. **Handle guardrail violations gracefully** with suggested actions
3. **Use appropriate user modes** (God for Mike, Demo for customers)
4. **Provide equipment context** for better AI diagnosis
5. **Rate limit awareness** - cache results when possible
6. **Log all tool executions** for audit trail
7. **Test in Demo mode** before deploying to customers

## Next Steps

1. Read the full [README.md](README.md) for detailed documentation
2. Review [example_integration.py](example_integration.py) for integration patterns
3. Run [test_tools.py](test_tools.py) to validate installation
4. Check [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md) for technical details

## Support

For issues or questions:
- Check the [README.md](README.md) documentation
- Review [example_integration.py](example_integration.py) for patterns
- Run tests with `python test_tools.py`
- Contact Mike for God Mode access requests

---

**Quick Reference:**

```python
# Initialize
registry = get_tool_registry(groq_api_key="...")

# Create context
context = ToolContext(user_id=42, chat_id=123, mode=UserMode.DEMO, ...)

# Execute tool
tool = registry.get("equipment")
result = await tool.execute_with_checks(params, context)

# Check result
if result.is_success:
    print(result.data)
```

That's it! You're ready to use PEPPER Tools. 🚀
