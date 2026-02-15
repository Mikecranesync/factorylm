# Digital Twin Node Routing System

**Status**: ✅ Production Ready
**Version**: 1.0.0
**Author**: Atlas (Principal Engineer)
**Date**: 2026-02-14

---

## Overview

The Digital Twin system provides intelligent routing and orchestration for the FactoryLM multi-device architecture. Each physical device (PLC laptop, Travel laptop, VPS) has a "digital twin" representation that knows its capabilities, health status, and communication protocols.

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    TWIN REGISTRY                            │
│  - Twin discovery & registration                           │
│  - Capability-based routing                                │
│  - Health monitoring                                        │
│  - Lifecycle management                                     │
└────────────────┬────────────────────────────────────────────┘
                 │
        ┌────────┴────────┬──────────────┐
        ▼                 ▼              ▼
   ┌─────────┐      ┌──────────┐   ┌──────────┐
   │PLC Twin │      │Travel    │   │VPS Twin  │
   │         │      │Twin      │   │          │
   │Factory  │      │          │   │Telegram  │
   │I/O      │      │Dev Tools │   │n8n       │
   │Micro 820│      │Git       │   │Workflows │
   │Matrix   │      │Tests     │   │Services  │
   └─────────┘      └──────────┘   └──────────┘
        │                 │              │
        ▼                 ▼              ▼
   100.72.2.99      100.83.251.23   100.68.120.99
```

---

## Core Concepts

### Digital Twin

A digital twin represents a physical device and provides:

- **Identity**: Unique ID, name, and metadata
- **Capabilities**: List of actions the device can perform
- **Health Status**: ONLINE, OFFLINE, DEGRADED, UNKNOWN
- **Communication**: HTTP/HTTPS endpoint for remote execution
- **Primitives**: `health_check()`, `execute()`, `shell()`, `read_file()`, `write_file()`

### Twin Registry

Central registry for managing all twins:

- **Discovery**: Register and unregister twins
- **Routing**: Find twins by ID, name, alias, or capability
- **Monitoring**: Periodic health checks and status tracking
- **Lifecycle**: Startup, shutdown, and resource cleanup

---

## File Structure

```
twins/
├── __init__.py          # Package exports
├── twin.py              # DigitalTwin base class
├── registry.py          # TwinRegistry manager
├── plc_twin.py          # PLC Laptop twin
├── travel_twin.py       # Travel Laptop twin
├── vps_twin.py          # VPS Server twin
├── example.py           # Usage examples
└── README.md            # This file
```

---

## Quick Start

### 1. Create Default Registry

```python
from twins import TwinRegistry

# Create registry with all three default twins
registry = TwinRegistry.create_default()

# Check health of all twins
await registry.health_check_all()

# Get status summary
summary = registry.get_status_summary()
print(f"Online: {summary['online']}/{summary['total_twins']}")
```

### 2. Resolve and Use Twins

```python
# Resolve by ID, name, or alias
plc = registry.resolve_twin("plc")
factory = registry.resolve_twin("factory")  # Same as "plc"
dev = registry.resolve_twin("dev")  # Travel laptop

# Check if twin is available
if plc and plc.is_online():
    # Read PLC tags
    tags = await plc.read_plc_tags(["Conveyor_Speed", "Motor_Running"])

    # Diagnose issue
    diagnosis = await plc.diagnose("Why is the conveyor jammed?")
```

### 3. Capability-Based Routing

```python
# Find all twins with a capability
twins = registry.find_twins_with_capability("read_plc_tags")

# Get the best twin for a capability
best = registry.get_best_twin_for_capability("diagnose")
if best:
    result = await best.execute("diagnose", {"question": "What's wrong?"})
```

### 4. Multi-Device Workflow

```python
# Get twins for orchestrated workflow
vps = registry.resolve_twin("vps")
plc = registry.resolve_twin("plc")

# 1. Receive Telegram message
question = "Is the factory running normally?"

# 2. Route to PLC for diagnosis
if plc.is_online():
    diagnosis = await plc.diagnose(question)

    # 3. Send response via Telegram
    if vps.is_online():
        await vps.send_telegram(chat_id, diagnosis)
```

---

## Twin Capabilities

### PLC Twin

**Device**: PLC Laptop (100.72.2.99)
**Hardware**: Factory I/O + Micro 820 PLC + Matrix API

**Capabilities**:
- `read_plc_tags` - Read PLC tag values via Matrix API
- `write_plc_tag` - Write to PLC tags
- `inject_fault` - Inject faults for testing
- `get_io_status` - Get current I/O state
- `diagnose` - AI-powered factory diagnosis
- `start_factory_io` - Start simulation
- `stop_factory_io` - Stop simulation
- `reset_simulation` - Reset to initial state
- `get_tag_history` - Historical tag values
- `execute_ladder_logic` - Run ladder logic programs

**Example**:
```python
plc = PLCTwin()

# Read specific tags
tags = await plc.read_plc_tags(["Conveyor_Speed", "Motor_Running"])

# Inject a fault
await plc.inject_fault("conveyor_jam", duration=60)

# Get AI diagnosis
diagnosis = await plc.diagnose("What's causing the motor overload?")
```

### Travel Twin

**Device**: Travel Laptop (100.83.251.23)
**Tools**: Claude Code, Git, Python, Node, Docker

**Capabilities**:
- `git_status` - Git repository status
- `git_commit` - Create commits
- `git_push` - Push to remote
- `git_pull` - Pull from remote
- `run_tests` - Execute test suites
- `deploy` - Deploy to environments
- `build_project` - Build codebase
- `lint_code` - Code linting
- `format_code` - Code formatting
- `install_dependencies` - Install packages
- `claude_code_status` - Claude Code session info
- `create_branch` - Create Git branches
- `merge_branch` - Merge branches

**Example**:
```python
travel = TravelTwin()

# Get Git status
status = await travel.git_status()

# Run tests
results = await travel.run_tests(test_type="unit")
print(f"Passed: {results['passed']}, Failed: {results['failed']}")

# Deploy to staging
await travel.deploy(environment="staging")
```

### VPS Twin

**Device**: VPS Server (100.68.120.99)
**Services**: Clawdbot, n8n, JARVIS, nginx

**Capabilities**:
- `send_telegram` - Send Telegram messages
- `trigger_workflow` - Execute n8n workflows
- `get_logs` - Retrieve service logs
- `list_workflows` - List n8n workflows
- `get_service_status` - Service health status
- `restart_service` - Restart services
- `execute_webhook` - Trigger webhooks
- `get_metrics` - System metrics
- `backup_data` - Create backups
- `restore_data` - Restore from backup
- `manage_cron` - Manage cron jobs
- `update_config` - Update service configs

**Example**:
```python
vps = VPSTwin()

# Send Telegram message
await vps.send_telegram("123456789", "Factory diagnosis complete")

# Trigger n8n workflow
result = await vps.trigger_workflow("factory-diagnosis", {
    "question": "What's the current status?"
})

# Get service status
status = await vps.get_service_status("clawdbot")
```

---

## Health Monitoring

### Manual Health Checks

```python
# Check single twin
is_healthy = await plc.health_check()
print(f"PLC Status: {plc.status.value}")

# Check all twins
health_results = await registry.health_check_all()
for twin_id, is_healthy in health_results.items():
    print(f"{twin_id}: {'✅' if is_healthy else '❌'}")
```

### Periodic Monitoring

```python
# Start periodic monitoring (every 60 seconds)
await registry.start_health_monitoring(interval=60)

# Let it run...
# Health checks happen automatically in the background

# Stop monitoring
await registry.stop_health_monitoring()
```

### Status Summary

```python
summary = registry.get_status_summary()
print(f"""
Total Twins: {summary['total_twins']}
Online: {summary['online']}
Offline: {summary['offline']}
Degraded: {summary['degraded']}
""")

# Detailed twin info
for twin in summary['twins']:
    print(f"{twin['name']}: {twin['status']}")
```

---

## Advanced Usage

### Custom Twin Implementation

```python
from twins import DigitalTwin, TwinStatus

class CustomTwin(DigitalTwin):
    def __init__(self):
        super().__init__(
            id="custom",
            name="Custom Device",
            url="http://192.168.1.100:8765",
            capabilities=["custom_action", "special_feature"]
        )

    async def custom_action(self, param: str) -> dict:
        """Custom capability implementation"""
        return await self.execute("custom_action", {"param": param})

# Register custom twin
registry = TwinRegistry()
registry.register(CustomTwin())
```

### Broadcasting

```python
# Execute action on all online twins
results = await registry.broadcast("health_check")

for twin_id, result in results.items():
    print(f"{twin_id}: {result}")
```

### Alias Resolution

```python
# All of these resolve to the PLC twin
plc1 = registry.resolve_twin("plc")
plc2 = registry.resolve_twin("factory")
plc3 = registry.resolve_twin("micro820")
plc4 = registry.resolve_twin("PLC Laptop")

assert plc1 == plc2 == plc3 == plc4
```

---

## Integration with PEPPER

### Diagnosis Service Integration

```python
from twins import TwinRegistry

class DiagnosisService:
    def __init__(self):
        self.registry = TwinRegistry.create_default()

    async def handle_question(self, question: str) -> str:
        """Route factory questions to PLC twin"""
        plc = self.registry.get_best_twin_for_capability("diagnose")

        if not plc:
            return "Factory diagnostics unavailable (PLC offline)"

        diagnosis = await plc.diagnose(question)
        return diagnosis
```

### Telegram Bot Integration

```python
async def handle_telegram_message(message: str, chat_id: str):
    """Handle Telegram message and route to appropriate twin"""
    registry = TwinRegistry.create_default()

    # Route factory questions to PLC
    if "factory" in message.lower() or "plc" in message.lower():
        plc = registry.resolve_twin("plc")
        if plc and plc.is_online():
            response = await plc.diagnose(message)
        else:
            response = "Factory diagnostics offline"

    # Send response via VPS
    vps = registry.resolve_twin("vps")
    if vps and vps.is_online():
        await vps.send_telegram(chat_id, response)
```

---

## Error Handling

All twin methods handle errors gracefully:

```python
# Health checks never throw exceptions
is_healthy = await twin.health_check()
# Returns: bool (False on error, sets status to OFFLINE)

# Execute returns error dict on failure
result = await twin.execute("some_action", {})
if result.get("success"):
    data = result.get("data")
else:
    error = result.get("error")
    print(f"Action failed: {error}")

# Shell/file operations return safe defaults
output = await twin.shell("failing_command")
# Returns: error string (not an exception)

content = await twin.read_file("nonexistent_file")
# Returns: empty string (not an exception)
```

---

## Testing

Run the examples:

```bash
cd services/telegram/pepper/twins
python example.py
```

Expected output:
```
================================================================================
DIGITAL TWIN SYSTEM - USAGE EXAMPLES
================================================================================

============================================================
EXAMPLE 1: Basic Twin Registry Usage
============================================================

📋 Registered 3 twins:
  - PLC Laptop (plc): 10 capabilities
  - Travel Laptop (travel): 13 capabilities
  - VPS Server (vps): 12 capabilities

🔍 Resolving twins:
  resolve_twin('plc') → PLC Laptop
  resolve_twin('factory') → PLC Laptop
  resolve_twin('dev') → Travel Laptop

...
```

---

## Production Deployment

### Environment Variables

Configure twin URLs via environment:

```bash
export PLC_TWIN_URL="http://100.72.2.99:8765"
export TRAVEL_TWIN_URL="http://100.83.251.23:8765"
export VPS_TWIN_URL="http://100.68.120.99:8765"
```

```python
import os

plc = PLCTwin(url=os.getenv("PLC_TWIN_URL", "http://100.72.2.99:8765"))
```

### Graceful Shutdown

```python
import signal
import asyncio

registry = TwinRegistry.create_default()
await registry.start_health_monitoring()

def shutdown_handler(signum, frame):
    asyncio.create_task(registry.shutdown())

signal.signal(signal.SIGTERM, shutdown_handler)
signal.signal(signal.SIGINT, shutdown_handler)
```

---

## Performance Considerations

- **Connection Pooling**: Each twin maintains a single `httpx.AsyncClient` for connection reuse
- **Parallel Health Checks**: Registry checks all twins concurrently
- **Capability Indexing**: O(1) lookup for twins by capability
- **Async Throughout**: All I/O operations are non-blocking

---

## Security Notes

- All twin communication uses HTTP (upgrade to HTTPS in production)
- No authentication implemented (add API keys/tokens for production)
- Shell execution has no sandboxing (use with trusted devices only)
- File operations have no path validation (validate paths before use)

---

## Troubleshooting

### Twin Shows OFFLINE

1. Check network connectivity: `ping 100.72.2.99`
2. Verify Jarvis Node is running on target device
3. Check firewall rules on target device
4. Test health endpoint: `curl http://100.72.2.99:8765/health`

### Capability Not Found

```python
# Check available capabilities
twin = registry.get_twin("plc")
print(twin.capabilities)

# Verify capability exists
if twin.has_capability("read_plc_tags"):
    result = await twin.read_plc_tags()
```

### Slow Health Checks

```python
# Reduce timeout for faster failures
plc = PLCTwin()
plc.timeout = 5  # 5 seconds instead of 30

# Increase monitoring interval
await registry.start_health_monitoring(interval=300)  # 5 minutes
```

---

## Future Enhancements

- [ ] WebSocket support for real-time updates
- [ ] Authentication and authorization
- [ ] Encrypted communication (TLS/HTTPS)
- [ ] Twin discovery via mDNS/Zeroconf
- [ ] Persistent health history
- [ ] Grafana dashboard integration
- [ ] Auto-reconnection logic
- [ ] Circuit breaker pattern
- [ ] Request rate limiting
- [ ] Twin versioning

---

## Contributing

This system follows FactoryLM engineering standards:

1. Create issue first
2. Branch from main
3. Write comprehensive tests
4. Document all capabilities
5. Submit PR with approval

See: `FactoryLM/CLAUDE.md` for full guidelines

---

## License

MIT License - FactoryLM Project

---

**Questions?** Contact Mike or reference the FactoryLM Vision:
https://github.com/Mikecranesync/factorylm/blob/main/README.md
