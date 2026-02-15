# FactoryLM Network Runbook

Operations guide for all machines in the FactoryLM network.

## Network Map

```
┌─────────────────────────────────────────────────────────────────┐
│                     TAILSCALE NETWORK                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────┐ │
│  │   PLC Laptop    │    │  Travel Laptop  │    │     VPS     │ │
│  │  100.72.2.99    │    │  100.83.251.23  │    │100.68.120.99│ │
│  │                 │    │                 │    │             │ │
│  │ - Factory I/O   │    │ - Claude Code   │    │ - Telegram  │ │
│  │ - Micro 820 PLC │    │ - Development   │    │ - n8n       │ │
│  │ - Jarvis Node   │    │ - Jarvis Node   │    │ - RemoteMe  │ │
│  │                 │    │                 │    │             │ │
│  │ NO SSH ACCESS   │    │ SSH + RDP OK    │    │ SSH OK      │ │
│  └─────────────────┘    └─────────────────┘    └─────────────┘ │
│                                                                 │
│  ┌─────────────────┐                                           │
│  │   Mike's Phone  │ ──── Telegram ──── All Bots               │
│  └─────────────────┘                                           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Machine Access Methods

### PLC Laptop (LAPTOP-0KA3C70H)
- **IP:** 100.72.2.99
- **SSH:** NO ACCESS
- **RDP:** Not configured
- **Access via:** Jarvis Node HTTP API only

```bash
# Health check
curl http://100.72.2.99:8765/health

# Run command
curl -X POST http://100.72.2.99:8765/shell \
  -H "Content-Type: application/json" \
  -d '{"command": "hostname", "timeout": 30}'

# Screenshot
curl http://100.72.2.99:8765/screenshot

# Read file
curl -X POST http://100.72.2.99:8765/files/read \
  -H "Content-Type: application/json" \
  -d '{"path": "C:/path/to/file"}'

# Write file
curl -X POST http://100.72.2.99:8765/files/write \
  -H "Content-Type: application/json" \
  -d '{"path": "C:/path/to/file", "content": "data"}'
```

### Travel Laptop (Miguelomaniac)
- **IP:** 100.83.251.23
- **SSH:** Yes (via Tailscale)
- **RDP:** Yes
- **User:** hharp

```bash
# SSH access
ssh hharp@100.83.251.23

# Jarvis Node API (same as PLC)
curl http://100.83.251.23:8765/health
```

### VPS (Jarvis/Ultron)
- **IP:** 100.68.120.99
- **SSH:** Yes
- **User:** jarvis (or root)

```bash
# SSH access
ssh jarvis@100.68.120.99

# Check services
ssh jarvis@100.68.120.99 "systemctl status remoteme"
```

---

## Services by Machine

### PLC Laptop Services

| Service | Port | Start Command | Check |
|---------|------|---------------|-------|
| Jarvis Node | 8765 | `python jarvis_node.py` | `curl :8765/health` |
| Matrix API | 8000 | `python -m matrix` | `curl :8000/api/health` |
| Factory I/O | - | Desktop app | Screenshot |

**Start Jarvis Node (via itself or Telegram):**
```bash
# From Travel laptop or VPS
curl -X POST http://100.72.2.99:8765/shell \
  -d '{"command": "cd C:/Users/hharp/remoteme-jarvis-node && python jarvis_node.py"}'
```

**If Jarvis Node is down:** Physical access required, or use RDP if configured.

### Travel Laptop Services

| Service | Port | Start Command | Check |
|---------|------|---------------|-------|
| Jarvis Node | 8765 | `python jarvis_node.py` | `curl :8765/health` |
| FRIDAY Bot | - | `doppler run -- python friday_bot.py` | Telegram |
| PEPPER Bot | - | `doppler run -- python run.py` | Telegram |

**Start Jarvis Node:**
```bash
cd C:\Users\hharp\remoteme-jarvis-node
python jarvis_node.py
```

**Start FRIDAY:**
```bash
cd C:\Users\hharp\OneDrive\Desktop\FactoryLM\services\telegram
doppler run --project voltron --config dev -- python friday_bot.py
```

**Start PEPPER:**
```bash
cd C:\Users\hharp\OneDrive\Desktop\FactoryLM\services\telegram\pepper
doppler run --project voltron --config dev -- python run.py
```

### VPS Services

| Service | Port | Start Command | Check |
|---------|------|---------------|-------|
| Jarvis Node | 8765 | `./start.sh` | `curl :8765/health` |
| RemoteMe API | 8100 | `uvicorn backend.main:app` | `curl :8100/health` |
| Gus Bot | - | `systemctl start factorylm-telegram` | Telegram |
| n8n | 5678 | `systemctl start n8n` | `curl :5678` |

**SSH and start services:**
```bash
ssh jarvis@100.68.120.99

# Start Jarvis Node
cd ~/remoteme-jarvis-node && ./start.sh

# Start RemoteMe
cd ~/remoteme && ./start.sh

# Start Gus via systemd
sudo systemctl start factorylm-telegram

# View logs
journalctl -u factorylm-telegram -f
```

---

## Telegram Bots

| Bot | Handle | Runs On | Start Command |
|-----|--------|---------|---------------|
| PEPPER | @Spicyclawd_bot | Travel | `doppler run -- python run.py` |
| FRIDAY | @FRIDAY_MCU_bot | Travel | `doppler run -- python friday_bot.py` |
| Gus | @FactoryLM_bot | VPS | `systemctl start factorylm-telegram` |
| RemoteMe | @JarvisMIO_bot | VPS | `cd ~/remoteme && ./start.sh` |

**Required env vars (all in Doppler):**
- `PEPPER_BOT_TOKEN`
- `FRIDAY_BOT_TOKEN`
- `TELEGRAM_BOT_TOKEN` (Gus)
- `REMOTEME_BOT_TOKEN`
- `GROQ_API_KEY`
- `ANTHROPIC_API_KEY`
- `SENTRY_DSN`
- `HONEYCOMB_API_KEY`

---

## Quick Diagnostics

### Check all nodes at once
```bash
# From any machine with curl
echo "PLC:"; curl -s http://100.72.2.99:8765/health | jq -r '.status // "OFFLINE"'
echo "Travel:"; curl -s http://100.83.251.23:8765/health | jq -r '.status // "OFFLINE"'
echo "VPS:"; curl -s http://100.68.120.99:8765/health | jq -r '.status // "OFFLINE"'
```

### Python one-liner
```bash
python -c "
import asyncio
from services.capabilities import get_capabilities
async def check():
    caps = get_capabilities()
    for nid, status in (await caps.nodes.check_all()).items():
        print(f'{nid}: {\"ONLINE\" if status.get(\"online\") else \"OFFLINE\"}')
asyncio.run(check())
"
```

### Via Telegram (any bot)
```
status
```

---

## Common Problems

### Bot not responding

1. **Check if bot process is running:**
   ```bash
   # On VPS
   ssh jarvis@100.68.120.99 "pgrep -f 'python.*bot'"

   # On Travel (via Jarvis Node)
   curl -X POST http://100.83.251.23:8765/shell \
     -d '{"command": "tasklist | findstr python"}'
   ```

2. **Check logs:**
   ```bash
   # VPS
   ssh jarvis@100.68.120.99 "journalctl -u factorylm-telegram -n 50"

   # Travel - check traces
   cat services/telegram/pepper/traces/$(date +%Y-%m-%d).jsonl | tail -20
   ```

3. **Restart bot:**
   ```bash
   # VPS
   ssh jarvis@100.68.120.99 "sudo systemctl restart factorylm-telegram"
   ```

### PLC Laptop offline

**If Jarvis Node is down, you need physical access.**

Check from another machine:
```bash
# Ping test
ping 100.72.2.99

# If ping works but API doesn't, Jarvis Node crashed
# Physical access required to restart
```

### Tailscale issues

```bash
# Check Tailscale status
tailscale status

# Reconnect
tailscale up

# Check if machine is in network
tailscale ping 100.72.2.99
```

### Doppler issues

```bash
# Check auth
doppler whoami

# Re-authenticate
doppler login

# Check project access
doppler configs --project voltron
```

---

## Deployment

### Deploy to VPS
```bash
# From Travel laptop
ssh jarvis@100.68.120.99 "cd ~/factorylm && git pull && ./restart.sh"
```

### Deploy to PLC Laptop (no SSH)
```bash
# Use Jarvis Node to pull code
curl -X POST http://100.72.2.99:8765/shell \
  -H "Content-Type: application/json" \
  -d '{"command": "cd C:/path/to/repo && git pull", "timeout": 60}'
```

### Sync Doppler secrets
```bash
doppler secrets download --project voltron --config prd --no-file --format env
```

---

## Emergency Contacts

- **Mike:** Telegram, Phone
- **Tailscale Admin:** https://login.tailscale.com/admin
- **Doppler Dashboard:** https://dashboard.doppler.com
- **Sentry Dashboard:** https://sentry.io
- **Honeycomb:** https://ui.honeycomb.io

---

## Scheduled Tasks

| Task | Frequency | Machine | Command |
|------|-----------|---------|---------|
| Health check | Every 5 min | VPS | Cron: `curl nodes/health` |
| Log rotation | Daily | All | logrotate |
| Backup traces | Daily | VPS | `tar -czf traces-$(date).tar.gz traces/` |

---

## Startup Sequence (Full Network)

1. **Ensure Tailscale is up on all machines**
2. **Start PLC Laptop services** (physical access or wake-on-LAN)
3. **Start VPS services:**
   ```bash
   ssh jarvis@100.68.120.99 "cd ~/remoteme-jarvis-node && ./start.sh"
   ssh jarvis@100.68.120.99 "sudo systemctl start factorylm-telegram"
   ```
4. **Start Travel Laptop services:**
   ```bash
   cd C:\Users\hharp\remoteme-jarvis-node && python jarvis_node.py
   ```
5. **Verify all nodes:**
   ```bash
   python tools/bot_capability_test.py watch
   ```
6. **Test via Telegram:**
   ```
   @JarvisMIO_bot: status
   ```
