# Demo UI Access Guide

**Service:** FactoryLM Demo UI (Fault Diagnosis Dashboard)
**Framework:** FastAPI + Uvicorn
**Port:** 8080
**Security:** Tailscale-only (private by default)

---

## Quick Access URLs

### From Any Tailscale Device

| URL | Description |
|-----|-------------|
| `http://laptop-0ka3c70h:8080` | MagicDNS name (recommended) |
| `http://100.72.2.99:8080` | Direct Tailscale IP |

### Device-Specific Instructions

| Device | How to Access |
|--------|---------------|
| **PLC Laptop** | `http://localhost:8080` |
| **Travel Laptop** | `http://laptop-0ka3c70h:8080` |
| **Phone (Pixel 9a)** | Open Tailscale app → ensure connected → open `http://laptop-0ka3c70h:8080` in browser |
| **VPS (ultron)** | `curl http://100.72.2.99:8080/health` |

---

## Phone Setup (One-Time)

1. **Install Tailscale** from Play Store / App Store
2. **Sign in** with your Google account (same as other devices)
3. **Connect** — tap the toggle to join the network
4. **Open browser** and go to: `http://laptop-0ka3c70h:8080`

Your phone's Tailscale name: `pixel-9a` (100.73.197.64)

---

## Service Management

### Start Demo UI on PLC Laptop

```powershell
# From PLC laptop directly
cd C:\Users\hharp\OneDrive\Desktop\FactoryLM\services\matrix
python demo_ui.py

# Or via SSH from travel laptop
ssh hharp@100.72.2.99 "cd 'C:\Users\hharp\OneDrive\Desktop\FactoryLM\services\matrix'; Start-Process python -ArgumentList 'demo_ui.py'"
```

### Stop Demo UI

```powershell
# From PLC laptop directly
Get-Process python | Where-Object { $_.CommandLine -like "*demo_ui*" } | Stop-Process

# Or via SSH
ssh hharp@100.72.2.99 "Get-Process python | Where-Object { $_.CommandLine -like '*demo_ui*' } | Stop-Process"
```

### Check Status

```bash
# Quick health check
curl http://laptop-0ka3c70h:8080/health

# Expected response:
# {"status":"ok","service":"factorylm-demo","matrix_api":"http://100.72.2.99:8000","nvidia_api":false}
```

---

## All-in-One Start Script (oc_plc)

The `start-oc-plc.ps1` script starts everything including Demo UI:

```powershell
# On PLC laptop
cd C:\Users\hharp\OneDrive\Desktop\FactoryLM\scripts\openclaw
.\start-oc-plc.ps1 -Background -WithFactoryIO
```

This starts:
- Factory I/O (if `-WithFactoryIO`)
- Matrix API (port 8000)
- Demo UI (port 8080)
- Jarvis Node (port 8765)

---

## Optional: Nice Domain Alias

### Option 1: Local Hosts File (per device)

Add to `C:\Windows\System32\drivers\etc\hosts` (Windows) or `/etc/hosts` (Linux/Mac):

```
100.72.2.99  factory-demo.local
100.72.2.99  oc-plc-demo.tail
```

Then access via: `http://factory-demo.local:8080`

### Option 2: Tailscale Alias (coming soon)

Tailscale is adding custom DNS aliases. Check: https://tailscale.com/kb/1054/dns

---

## Security Notes

1. **Tailscale-only** — Only devices on your Tailscale network can access
2. **No public exposure** — Port 8080 is NOT open to the internet
3. **Authentication** — Tailscale handles device auth via your Google account
4. **Encryption** — All traffic is encrypted via WireGuard

---

## Option B: Temporary Public Access (For Demos)

If you need to share with someone outside Tailscale:

### Using Tailscale Funnel (Recommended)

```bash
# On PLC laptop (one-time setup)
tailscale funnel 8080

# This creates a public URL like:
# https://laptop-0ka3c70h.tail12345.ts.net/
```

To disable:
```bash
tailscale funnel --off
```

### Using Cloudflare Tunnel (Alternative)

```bash
# Install cloudflared
cloudflared tunnel --url http://localhost:8080

# This creates a temporary public URL
# Share the URL, and kill the process when done
```

---

## Troubleshooting

### "Connection refused"
- Check Demo UI is running: `ssh hharp@100.72.2.99 "netstat -an | findstr ':8080'"`
- Start it: `ssh hharp@100.72.2.99 "cd 'C:\Users\hharp\OneDrive\Desktop\FactoryLM\services\matrix'; Start-Process python -ArgumentList 'demo_ui.py'"`

### "Cannot resolve laptop-0ka3c70h"
- Ensure MagicDNS is enabled in Tailscale admin: https://login.tailscale.com/admin/dns
- Use IP directly: `http://100.72.2.99:8080`

### Phone can't connect
- Check Tailscale app shows "Connected"
- Try IP instead of hostname: `http://100.72.2.99:8080`

---

*FactoryLM — "Text your factory, AI tells you what's wrong."*
