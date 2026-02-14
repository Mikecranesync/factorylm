# OpenClaw Distributed Agent Pattern

**One Agent Per Machine** — A pattern for deploying factory-aware AI agents across devices.

---

## Architecture Overview

```
                    ┌─────────────────────────────────────────┐
                    │              TELEGRAM                    │
                    │         (Mike's phone)                   │
                    └───────────────┬─────────────────────────┘
                                    │
                                    ▼
                    ┌─────────────────────────────────────────┐
                    │           THIN TELEGRAM BOT              │
                    │     (routes /to commands to agents)      │
                    │          @UltronVPS_bot                  │
                    └───────────────┬─────────────────────────┘
                                    │
              ┌─────────────────────┼─────────────────────┐
              ▼                     ▼                     ▼
    ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
    │   oc_travel     │   │    oc_plc       │   │    oc_vps       │
    │ 100.83.251.23   │   │  100.72.2.99    │   │ 100.68.120.99   │
    │   Port 8765     │   │   Port 8765     │   │   Port 8765     │
    ├─────────────────┤   ├─────────────────┤   ├─────────────────┤
    │ Tools:          │   │ Tools:          │   │ Tools:          │
    │ - Matrix API    │   │ - Modbus TCP    │   │ - Claude Code   │
    │ - Git/Code      │   │ - Factory I/O   │   │ - Shell access  │
    │ - Claude Code   │   │ - Jarvis Node   │   │ - Telegram API  │
    │ - Web access    │   │ - Matrix API    │   │ - Matrix API    │
    └─────────────────┘   └─────────────────┘   └─────────────────┘
```

---

## Instance Definitions

| Instance | Codename | Machine | Tailscale IP | Purpose |
|----------|----------|---------|--------------|---------|
| `oc_travel` | Travel | Windows laptop | 100.83.251.23 | Development, testing, demos |
| `oc_plc` | PLC | Windows laptop | 100.72.2.99 | Factory I/O, Micro820, real PLC |
| `oc_vps` | VPS | DigitalOcean | 100.68.120.99 | Always-on gateway, Telegram |

---

## Message Routing

### Syntax
```
/to <instance> <message>
/to travel show me IO for the conveyor
/to plc what faults are active?
/to vps restart the diagnosis service
```

### Routing Logic (Thin Bot)
```python
# In Telegram gateway bot
def route_message(text: str) -> tuple[str, str]:
    """Parse /to command and return (instance, message)"""
    if text.startswith("/to "):
        parts = text[4:].split(" ", 1)
        instance = parts[0].lower()
        message = parts[1] if len(parts) > 1 else ""

        instances = {
            "travel": "http://100.83.251.23:8765",
            "plc": "http://100.72.2.99:8765",
            "vps": "http://localhost:18789"  # Local on VPS
        }

        if instance in instances:
            return instances[instance], message

    # Default: route to VPS (main brain)
    return "http://localhost:18789", text
```

---

## Config Pattern

Each OpenClaw instance has:

1. **Identity file** — `~/.openclaw/IDENTITY.md`
2. **Config file** — `~/.openclaw/openclaw.json`
3. **Workspace** — `~/.openclaw/workspace/`
4. **Agent data** — `~/.openclaw/agents/main/agent/`

### oc_travel Config

```json
{
  "meta": {
    "instanceId": "oc_travel",
    "hostname": "Miguelomaniac",
    "role": "development"
  },
  "agents": {
    "defaults": {
      "model": {
        "primary": "anthropic/claude-opus-4-5-20250514",
        "fallbacks": ["groq/llama-3.3-70b-versatile"]
      },
      "workspace": "C:\\Users\\hharp\\.openclaw\\workspace"
    }
  },
  "tools": {
    "matrix_api": {
      "url": "http://100.72.2.99:8000",
      "description": "PLC tag database on factory laptop"
    },
    "jarvis_node": {
      "url": "http://100.72.2.99:8765",
      "description": "Remote execution on PLC laptop"
    }
  },
  "gateway": {
    "port": 8765,
    "mode": "local",
    "bind": "0.0.0.0"
  }
}
```

### oc_plc Config

```json
{
  "meta": {
    "instanceId": "oc_plc",
    "hostname": "LAPTOP-0KA3C70H",
    "role": "factory-floor"
  },
  "agents": {
    "defaults": {
      "model": {
        "primary": "groq/llama-3.3-70b-versatile",
        "fallbacks": ["ollama/qwen2.5:0.5b"]
      },
      "workspace": "C:\\Users\\hharp\\.openclaw\\workspace"
    }
  },
  "tools": {
    "modbus_tcp": {
      "host": "localhost",
      "port": 502,
      "description": "Direct Modbus to Micro820 PLC"
    },
    "factory_io": {
      "path": "C:\\Program Files (x86)\\Real Games\\Factory IO",
      "description": "Factory I/O simulation"
    },
    "matrix_api": {
      "url": "http://localhost:8000",
      "description": "Local Matrix API"
    }
  },
  "gateway": {
    "port": 8765,
    "mode": "local",
    "bind": "0.0.0.0"
  }
}
```

### oc_vps Config

```json
{
  "meta": {
    "instanceId": "oc_vps",
    "hostname": "ultron",
    "role": "gateway"
  },
  "agents": {
    "defaults": {
      "model": {
        "primary": "anthropic/claude-sonnet-4-20250514",
        "fallbacks": ["groq/llama-3.1-8b-instant"]
      },
      "workspace": "/root/jarvis-workspace"
    }
  },
  "tools": {
    "travel_node": {
      "url": "http://100.83.251.23:8765",
      "description": "Travel laptop Jarvis node"
    },
    "plc_node": {
      "url": "http://100.72.2.99:8765",
      "description": "PLC laptop Jarvis node"
    }
  },
  "channels": {
    "telegram": {
      "enabled": true,
      "botToken": "YOUR_BOT_TOKEN",
      "dmPolicy": "allowlist",
      "allowFrom": ["8445149012"]
    }
  },
  "gateway": {
    "port": 18789
  }
}
```

---

## Identity Files

Each instance has an IDENTITY.md that tells the agent who it is:

### oc_travel IDENTITY.md
```markdown
# Identity: oc_travel

You are the **Travel Laptop Agent** in the FactoryLM network.

## Your Role
- Development and testing
- Code changes and commits
- Presentation demos
- Remote debugging

## Your Tools
- Full Claude Code access
- Git repositories
- Web browsing
- Matrix API (via PLC laptop)

## Your Siblings
- oc_plc (100.72.2.99) — Factory floor, has real PLC
- oc_vps (100.68.120.99) — Always-on gateway

## When Asked About Factory
If asked about live PLC data, fetch from Matrix API at http://100.72.2.99:8000
```

### oc_plc IDENTITY.md
```markdown
# Identity: oc_plc

You are the **PLC Laptop Agent** in the FactoryLM network.

## Your Role
- Direct hardware access
- Factory I/O simulation
- Micro820 PLC connection
- Real-time tag monitoring

## Your Tools
- Modbus TCP (port 502)
- Factory I/O simulator
- Matrix API (local)
- Jarvis Node (shell access)

## Your Siblings
- oc_travel (100.83.251.23) — Development
- oc_vps (100.68.120.99) — Gateway

## Safety
NEVER write to PLC registers without explicit confirmation.
You are in READ-ONLY mode for pilot deployments.
```

---

## Service Scripts

### Windows (oc_travel, oc_plc)

**Start script** — `start-oc-instance.ps1`
```powershell
# Start OpenClaw instance for FactoryLM
$instanceId = $env:OC_INSTANCE_ID ?? "oc_travel"
Write-Host "Starting OpenClaw instance: $instanceId"

# Set environment
$env:OC_CONFIG = "$env:USERPROFILE\.openclaw\openclaw.json"
$env:OC_IDENTITY = "$env:USERPROFILE\.openclaw\IDENTITY.md"

# Start Jarvis Node (HTTP API)
Start-Process python -ArgumentList "jarvis_node.py" -WorkingDirectory "C:\Users\hharp\OneDrive\Desktop\FactoryLM\remoteme-jarvis-node"

# Log startup
Add-Content -Path "$env:USERPROFILE\.openclaw\logs\startup.log" -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $instanceId started"
```

### Linux (oc_vps)

**Systemd unit** — `oc-vps.service`
```ini
[Unit]
Description=OpenClaw VPS Agent (oc_vps)
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root
Environment=OC_INSTANCE_ID=oc_vps
Environment=OC_CONFIG=/root/.openclaw/openclaw.json
ExecStart=/usr/local/bin/openclaw gateway
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

---

## Deployment Steps

### 1. oc_travel (This Laptop)

```powershell
# Create directories
mkdir -Force "$env:USERPROFILE\.openclaw"
mkdir -Force "$env:USERPROFILE\.openclaw\workspace"
mkdir -Force "$env:USERPROFILE\.openclaw\logs"

# Copy config
cp scripts\openclaw\oc_travel.json "$env:USERPROFILE\.openclaw\openclaw.json"
cp scripts\openclaw\IDENTITY_travel.md "$env:USERPROFILE\.openclaw\IDENTITY.md"

# Start Jarvis Node
python remoteme-jarvis-node\jarvis_node.py
```

### 2. oc_plc (PLC Laptop)

```powershell
# SSH to PLC laptop
ssh hharp@100.72.2.99

# Create directories
mkdir -Force "$env:USERPROFILE\.openclaw"
mkdir -Force "$env:USERPROFILE\.openclaw\workspace"

# Deploy config (via SCP from travel laptop)
scp scripts/openclaw/oc_plc.json hharp@100.72.2.99:~/.openclaw/openclaw.json
scp scripts/openclaw/IDENTITY_plc.md hharp@100.72.2.99:~/.openclaw/IDENTITY.md

# Start services
python jarvis_node.py
python services/matrix/app.py
```

### 3. oc_vps (VPS)

```bash
# SSH to VPS
ssh root@100.68.120.99

# Deploy config
scp scripts/openclaw/oc_vps.json root@100.68.120.99:/root/.openclaw/openclaw.json
scp scripts/openclaw/IDENTITY_vps.md root@100.68.120.99:/root/.openclaw/IDENTITY.md

# Enable systemd service
systemctl enable oc-vps
systemctl start oc-vps
```

---

## Testing the Pattern

```bash
# From Telegram:
/to travel what is your identity?
/to plc show me IO
/to vps check status of all nodes

# Expected: Each agent responds with its role-specific knowledge
```

---

## Next Steps

1. [ ] Implement thin routing bot on VPS
2. [ ] Create MCP tool for cross-agent communication
3. [ ] Add health monitoring across all instances
4. [ ] Implement task handoff (travel → plc for hardware tasks)

---

*Pattern designed for FactoryLM pilot deployment*
