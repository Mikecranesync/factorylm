# PLC Laptop Remote Setup

**Last Updated:** 2026-02-13  
**Status:** Working — SSH over Tailscale, ready for Cosmos Cookoff demo

---

## Laptop Inventory

| Property | Value |
|----------|-------|
| **Hostname** | LAPTOP-0KA3C70H |
| **User** | hharp |
| **Tailscale IP** | 100.72.2.99 |
| **OS** | Windows 10/11 |
| **Python** | 3.14.2 (`C:\Users\hharp\AppData\Local\Python\bin\python.exe`, also on PATH as `python`) |
| **pip** | Works via `python -m pip` (bare `pip` may not be on PATH) |
| **Git** | GitHub Desktop only — `C:\Users\hharp\AppData\Local\GitHubDesktop\app-3.5.4\resources\app\git\cmd\git.exe` |
| **Docker** | ❌ Not installed |
| **Repo Path** | `C:\Users\hharp\Desktop\factorylm-monorepo` |
| **Current Branch** | `feat/whatsapp-adapter-setup` |

### Installed pip Packages

| Package | Version | Status |
|---------|---------|--------|
| fastapi | 0.128.0 | ✅ Installed |
| uvicorn | 0.40.0 | ✅ Installed |
| pymodbus | 3.11.4 | ✅ Installed |
| httpx | — | ❌ Missing (needed by bridge + watcher) |
| PyYAML | — | ❌ Missing (needed by bridge config loader) |

Run `.\scripts\plc_remote.ps1 deps` to install the missing packages.

---

## SSH Connection

The PLC laptop runs Tailscale and accepts key-based SSH (no password prompt).

```powershell
# Interactive shell
ssh hharp@100.72.2.99

# Run a single command
ssh hharp@100.72.2.99 "hostname"
```

### What is the Tailscale IP?

`100.72.2.99` is a **Tailscale** mesh VPN address. It works from any machine on the same Tailscale network, regardless of physical location — home, office, coffee shop, etc. No port forwarding or firewall rules needed.

### Remote Shell Notes

- The remote shell is **PowerShell** (not cmd.exe, not bash).
- Use `;` to chain commands (not `&&`).
- Paths use backslashes: `C:\Users\hharp\Desktop\...`
- Escape `$` in remote commands when needed: `` `$variable ``

---

## What's Installed vs What's Missing

| Tool | Available? | Notes |
|------|-----------|-------|
| Python 3.14 | ✅ | Via WindowsApps, on PATH |
| pip | ✅ | Use `python -m pip`, not bare `pip` |
| fastapi + uvicorn | ✅ | Can run Matrix API |
| pymodbus | ✅ | Can connect to Factory I/O Modbus |
| httpx | ❌ | Required by bridge and watcher |
| PyYAML | ❌ | Required by bridge config loader |
| Git (standalone) | ❌ | Only via GitHub Desktop executable |
| Docker | ❌ | Not needed for the Cookoff demo |
| Factory I/O | ✅ | Installed, license active |
| Tailscale | ✅ | Connected, IP 100.72.2.99 |
| SSH Server | ✅ | OpenSSH, key-based auth working |

---

## Remote Management Script

All remote operations are handled by `scripts/plc_remote.ps1`. Run it from the **dev machine** (not the PLC laptop).

### Commands

| Command | Description |
|---------|-------------|
| `status` | Check SSH, Python, pip packages, repo branch, running processes |
| `sync` | Git pull latest code on the PLC laptop |
| `deps` | Install missing pip packages (httpx, pyyaml) |
| `start-matrix` | Start the Matrix API (port 8000) |
| `start-bridge` | Start the Factory I/O bridge (default: sim mode) |
| `start-watcher` | Start the Cosmos incident watcher |
| `start-all` | Start all three services in sequence |
| `stop-all` | Kill all Python processes on the PLC laptop |
| `logs` | Tail recent log output (default: matrix) |
| `check-factoryio` | Check if Factory I/O is running |

### Examples

```powershell
# Check everything is reachable and ready
.\scripts\plc_remote.ps1 status

# Install missing dependencies
.\scripts\plc_remote.ps1 deps

# Pull latest code
.\scripts\plc_remote.ps1 sync

# Start all 3 services (Matrix, Bridge in sim mode, Watcher)
.\scripts\plc_remote.ps1 start-all

# Start bridge in Modbus mode (connects to Factory I/O)
.\scripts\plc_remote.ps1 start-bridge ""

# Start bridge with custom args
.\scripts\plc_remote.ps1 start-bridge "--plc-host 192.168.1.100 --interval 200"

# View Matrix API logs
.\scripts\plc_remote.ps1 logs matrix

# View bridge logs
.\scripts\plc_remote.ps1 logs bridge

# View watcher logs
.\scripts\plc_remote.ps1 logs watcher

# Stop everything
.\scripts\plc_remote.ps1 stop-all

# Is Factory I/O running on the laptop?
.\scripts\plc_remote.ps1 check-factoryio
```

### Log Files

All service logs are written to `C:\Users\hharp\Desktop\factorylm-monorepo\logs\` on the PLC laptop:

| File | Service |
|------|---------|
| `matrix-stdout.log` / `matrix-stderr.log` | Matrix API |
| `bridge-stdout.log` / `bridge-stderr.log` | Factory I/O bridge |
| `watcher-stdout.log` / `watcher-stderr.log` | Cosmos watcher |

---

## Pre-Flight Checklist (Cosmos Cookoff Demo)

Run this before demoing on the PLC laptop:

```
[ ] 1. Tailscale connected on both machines
       → .\scripts\plc_remote.ps1 status (should show hostname)

[ ] 2. Missing pip packages installed
       → .\scripts\plc_remote.ps1 deps

[ ] 3. Repo up to date
       → .\scripts\plc_remote.ps1 sync

[ ] 4. No stale Python processes running
       → .\scripts\plc_remote.ps1 stop-all

[ ] 5. (Optional) Factory I/O running with Modbus enabled
       → .\scripts\plc_remote.ps1 check-factoryio
       → If not using Factory I/O, sim mode works fine

[ ] 6. Start all services
       → .\scripts\plc_remote.ps1 start-all

[ ] 7. Verify Matrix API is reachable
       → Open http://100.72.2.99:8000 in browser
       → Should show the FactoryLM Matrix dashboard

[ ] 8. Verify tags are flowing
       → .\scripts\plc_remote.ps1 logs bridge
       → Should see "Posted N snapshots" or sim output

[ ] 9. Inject a fault and verify Cosmos analysis
       → curl -X POST http://100.72.2.99:8000/api/tags -H "Content-Type: application/json" -d '{"timestamp":"2026-02-13T10:00:00Z","node_id":"sim-micro820","motor_running":true,"motor_speed":60,"motor_current":8.5,"temperature":35.0,"pressure":100,"conveyor_running":true,"conveyor_speed":0,"sensor_1":true,"sensor_2":false,"fault_alarm":true,"e_stop":false,"error_code":3,"error_message":"Conveyor jam"}'
       → .\scripts\plc_remote.ps1 logs watcher
       → Should see "Analyzing incident #1: Conveyor jam"
```

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `ssh: connect to host 100.72.2.99 port 22: Connection refused` | Tailscale not running on one or both machines. Run `tailscale status` locally. |
| `ssh: Permission denied` | SSH key not set up. Copy key: `type $env:USERPROFILE\.ssh\id_rsa.pub \| ssh hharp@100.72.2.99 "Add-Content ~\.ssh\authorized_keys"` |
| `python: command not found` on remote | Python not on PATH. Try full path: `C:\Users\hharp\AppData\Local\Python\bin\python.exe` |
| `pip: command not found` | Always use `python -m pip`, never bare `pip` |
| Git pull fails | The git exe path may have changed if GitHub Desktop updated. SSH in and check: `Get-ChildItem "C:\Users\hharp\AppData\Local\GitHubDesktop\app-*"` |
| `&&` doesn't work in remote commands | Remote shell is PowerShell — use `;` to chain commands |
| Matrix API port 8000 already in use | `.\scripts\plc_remote.ps1 stop-all` then retry |
| Services start but immediately exit | Check stderr logs: `.\scripts\plc_remote.ps1 logs matrix` or `logs bridge` |
| `ModuleNotFoundError: httpx` | Run `.\scripts\plc_remote.ps1 deps` to install missing packages |
| Can't reach http://100.72.2.99:8000 | Windows Firewall may block port 8000. SSH in and run: `New-NetFirewallRule -DisplayName "Matrix API" -Direction Inbound -Port 8000 -Protocol TCP -Action Allow` |
| Factory I/O Modbus connection refused | Verify Factory I/O is running with Modbus driver enabled. Check `.\scripts\plc_remote.ps1 check-factoryio` |
| Repo is on wrong branch | SSH in: `Set-Location C:\Users\hharp\Desktop\factorylm-monorepo; & 'C:\Users\hharp\AppData\Local\GitHubDesktop\app-3.5.4\resources\app\git\cmd\git.exe' checkout main` |

---

## Architecture Reference

```
Dev Machine (this PC)                     PLC Laptop (100.72.2.99)
┌──────────────────────┐                  ┌──────────────────────────────────┐
│                      │    Tailscale     │  factorylm-monorepo/             │
│  scripts/            │    SSH (22)      │                                  │
│    plc_remote.ps1 ───┼──────────────────┼─► Matrix API     (:8000)        │
│                      │                  │   FactoryIO Bridge (sim/Modbus) │
│  Browser ────────────┼──── HTTP :8000 ──┼─► Cosmos Watcher               │
│                      │                  │                                  │
└──────────────────────┘                  │  Factory I/O (optional)         │
                                          │    └─ Modbus TCP :502           │
                                          └──────────────────────────────────┘
```
