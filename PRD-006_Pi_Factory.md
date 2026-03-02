# PRD-006: Pi Factory — Zero-Config PLC Discovery Appliance
## Phase 5: Factory Floor Deployment

**Domain:** factorylm.com
**GitHub:** github.com/factorylm/plc-client
**Product:** Pi Factory (Industrial Discovery Appliance)
**Version:** 0.6.0
**Depends On:** PRD-003 (plc-client base), PRD-005 (Factory I/O integration)
**Status:** PRE-BUILD — Appliance Hardening Phase

---

## Executive Summary

Pi Factory is a zero-config Raspberry Pi appliance that auto-discovers every PLC on a factory subnet and shows live I/O in a browser. It is the first FactoryLM product that ships to a factory floor rather than a developer's laptop.

- Plug a Pi into any factory Ethernet switch
- Within 60 seconds, open `http://pi-factory.local:8000`
- See every Modbus TCP and EtherNet/IP device on the subnet, live

**This is the product. The library (PRD-003/005) is plumbing. This is what a maintenance tech uses.**

---

## Architecture

```
Factory LAN (192.168.1.0/24)
┌───────────────────────────────────────────────────────────────┐
│                                                               │
│   ┌──────────┐    ┌──────────┐    ┌──────────┐               │
│   │ Micro820 │    │ CompactLX│    │ Other PLC│               │
│   │ :502     │    │ :44818   │    │ :502     │               │
│   └────┬─────┘    └────┬─────┘    └────┬─────┘               │
│        │               │               │                     │
│   ─────┴───────────────┴───────────────┴──── Factory Switch  │
│                         │                                     │
│                    ┌────┴─────┐                               │
│                    │ Pi       │  ← Pi Factory Appliance       │
│                    │ Factory  │    Hostname: pi-factory        │
│                    │ :8000    │    mDNS: pi-factory.local     │
│                    └──────────┘    Avahi: _factorylm._tcp     │
│                                                               │
└───────────────────────────────────────────────────────────────┘
         │
         │  Any browser on the LAN
         ▼
    ┌──────────────────────────┐
    │  http://pi-factory.local │
    │  :8000                   │
    │                          │
    │  ┌────────┐ ┌────────┐  │
    │  │Micro820│ │CompactLX│  │  ← Live device cards
    │  │coils   │ │tags     │  │     SSE real-time updates
    │  │regs    │ │I/O      │  │     Flash-on-change
    │  └────────┘ └────────┘  │
    └──────────────────────────┘
```

---

## Hardware BOM

| Item | Spec | Notes |
|------|------|-------|
| Raspberry Pi | Pi 4 Model B (2GB+ RAM) or Pi 5 | Pi 3B+ minimum but not recommended |
| SD Card | 32GB+ Class 10 / A1 | Pre-flash Ubuntu Server 24.04 LTS (64-bit) |
| Ethernet | Cat5e cable to factory switch | **Wi-Fi NOT recommended** for industrial |
| Power | USB-C 5V/3A (Pi 4) or 5V/5A (Pi 5) | Use official PSU for reliability |
| Case (optional) | DIN-rail mount enclosure | For panel mounting in electrical cabinets |

**Total cost: ~$75 USD** (Pi 4 2GB + SD + case + cable + PSU)

---

## Zero-Config Install

The existing `deploy/setup-pi-factory.sh` performs a 6-step unattended install:

### Step 1: System Packages
```bash
sudo apt-get install -y avahi-daemon avahi-utils python3 python3-venv python3-pip
```

### Step 2: Hostname
Sets hostname to `pi-factory` via `hostnamectl` and updates `/etc/hosts`.

### Step 3: DHCP + Link-Local Fallback
Writes `/etc/netplan/99-pi-factory.yaml`:
```yaml
network:
  version: 2
  renderer: networkd
  ethernets:
    eth0:
      dhcp4: true
      dhcp4-overrides:
        route-metric: 100
      link-local: [ipv4]
      optional: true
```
If no DHCP server exists on the network, systemd-networkd assigns an automatic `169.254.x.x` link-local address and the Pi is still reachable.

### Step 4: Avahi mDNS
Installs `/etc/avahi/services/pi-factory.service` which advertises:
- `_factorylm._tcp` on port 8000 (custom service type)
- `_http._tcp` on port 8000 (generic HTTP)
- Hostname: `pi-factory.local`

### Step 5: Python Environment
Creates a venv at `$INSTALL_DIR/.venv` and installs:
- `pymodbus >= 3.6.0`
- `fastapi >= 0.104.0`
- `uvicorn[standard] >= 0.24.0`
- `pydantic-settings >= 2.0.0`

### Step 6: Systemd Service
Installs `pi-factory.service`:
- Runs `uvicorn backend.main:app --host 0.0.0.0 --port 8000`
- Starts after `network-online.target` and `avahi-daemon.service`
- `Restart=on-failure` with 5-second delay
- `FACTORYLM_DISCOVERY_ENABLED=true` environment variable

### Bootstrap Command
```bash
# From a fresh Raspberry Pi OS install:
git clone https://github.com/factorylm/plc-client.git ~/factorylm/services/plc-modbus
cd ~/factorylm/services/plc-modbus
bash deploy/setup-pi-factory.sh
```

---

## Network Architecture

| Layer | Config | Fallback |
|-------|--------|----------|
| **IP** | DHCP on `eth0` (Netplan + systemd-networkd) | Automatic `169.254.x.x/16` link-local (no server needed) |
| **DNS** | mDNS via Avahi | Direct IP access always works |
| **Hostname** | `pi-factory.local` | Avahi auto-resolves on Linux/macOS/Windows |
| **Service** | `_factorylm._tcp` on port 8000 | `_http._tcp` also advertised |

### Scanning Behavior
- **Subnet:** `/24` sweep (e.g. `192.168.1.1` through `192.168.1.254`)
- **Modbus TCP:** Port 502 probe with 0.3s timeout
- **EtherNet/IP:** Port 44818 probe → `pycomm3.LogixDriver` connect → tag list + batch read
- **Concurrency:** Up to 50 parallel workers (`scanner_max_workers`)
- **Interval:** 30-second rescan cycle (`discovery_scan_interval`)

### How Discovery Works
1. Pi boots, gets DHCP (or link-local fallback)
2. Avahi advertises `pi-factory.local` on the LAN
3. `discovery_daemon.py` starts scanning the local `/24` subnet
4. TCP connect probe on 502 and 44818 for each host
5. Successful connections → device added to in-memory device list
6. Tag polling begins at 0.5-second intervals (`discovery_poll_interval`)
7. Devices that miss 3 consecutive polls → marked offline
8. SSE stream pushes device state to all connected browsers

---

## Dashboard

The dashboard is `backend/static/index.html` — a 210-line single-page app served by FastAPI.

### Features
- **SSE connection** to `/api/stream` for real-time tag updates
- **Per-device cards** with tag name/value tables
- **Color-coded status:** green dot = polling, yellow = online, red = offline
- **Flash animation** on value changes (brief highlight when a tag value changes)
- **Color-coded booleans:** green = TRUE, default = FALSE
- **Mobile responsive:** single-column layout on small screens
- **Empty state:** spinner + "Scanning for PLCs..." when no devices found yet
- **Last update timestamp** in header

### No-feature list (intentional V1 omissions)
- No login/authentication
- No historical data or charts
- No chat interface
- No database
- No configuration UI

---

## API Surface

All endpoints are prefixed with `/api` (configurable via `FACTORYLM_API_PREFIX`).

### Health & Diagnostics

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Returns `{"status": "healthy", "version": "0.1.0"}` |
| GET | `/api/tracing-health` | OpenTelemetry tracing status (no-op if not installed) |

### PLC Operations (Modbus)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/plc/status` | PLC connection status |
| GET | `/api/plc/io` | Current I/O snapshot (coils + registers) |
| POST | `/api/plc/connect` | Connect to a specific PLC by host:port |
| POST | `/api/plc/write-coil` | Write a boolean coil value |

### Discovery (EtherNet/IP + Modbus)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/devices` | List all discovered devices with status |
| GET | `/api/devices/{ip}/tags` | Read tags for a specific device |
| GET | `/api/stream` | SSE event stream — `tags` events with full device data |

### Network Setup

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/setup/scan-network` | Trigger a manual network scan |

### WebSocket

| Method | Path | Description |
|--------|------|-------------|
| WS | `/ws/io` | WebSocket for real-time I/O (alternative to SSE) |

### Dashboard

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Serves `static/index.html` — the live dashboard |

---

## Configuration

All settings are environment variables prefixed with `FACTORYLM_`:

| Variable | Default | Description |
|----------|---------|-------------|
| `FACTORYLM_MOCK_MODE` | `false` | Use simulated PLC, disable discovery |
| `FACTORYLM_DISCOVERY_ENABLED` | `true` | Enable auto-discovery daemon |
| `FACTORYLM_DISCOVERY_SCAN_INTERVAL` | `30` | Seconds between subnet rescans |
| `FACTORYLM_DISCOVERY_POLL_INTERVAL` | `0.5` | Seconds between tag polls per device |
| `FACTORYLM_DISCOVERY_PORT` | `8000` | HTTP server port |
| `FACTORYLM_SCANNER_DEFAULT_SUBNET` | `192.168.1` | Subnet to scan (first 3 octets) |
| `FACTORYLM_SCANNER_DEFAULT_TIMEOUT` | `0.3` | TCP probe timeout in seconds |
| `FACTORYLM_SCANNER_MAX_WORKERS` | `50` | Parallel scan threads |
| `FACTORYLM_CORS_ORIGINS` | `["*"]` | Allowed CORS origins |

---

## Mock Mode

For demos, trade shows, and development without hardware:

```bash
FACTORYLM_MOCK_MODE=true uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

In mock mode:
- Discovery daemon is **disabled** (no network scanning)
- A `MockPLC` is auto-connected at startup
- `/api/plc/io` returns simulated data that changes over time
- Dashboard works normally against the mock data
- All other endpoints remain functional

---

## Edge Mode (Future — Not V1 Scope)

The `factorylm-edge/` directory contains a **separate concept**: a Modbus TCP *server* that turns a Pi into a virtual PLC via GPIO.

### What It Does
- `edge_server.py` — pymodbus `StartAsyncTcpServer` on port 502
- `gpio_mapping.py` — 5 pre-built Factory I/O scene configs:
  - `sorting_basic` — Sorting by Height
  - `pick_and_place` — Pick & Place
  - `assembler` — Assembler
  - `level_control` — Level Control
  - `micro820_mirror` — Mirror a real Micro 820

### How It Differs From Pi Factory
| | Pi Factory (this PRD) | Edge Mode |
|-|----------------------|-----------|
| Pi acts as | PLC **viewer** (client) | PLC **emulator** (server) |
| Modbus role | TCP Client → reads PLCs | TCP Server → other clients read it |
| GPIO | Not used | Bridges Modbus coils to physical pins |
| Network | Scans subnet for PLCs | Listens for incoming Modbus connections |
| Port | 8000 (HTTP) | 502 (Modbus TCP) |

Edge Mode is documented here for context but is **not part of V1 scope**. It will get its own PRD if/when it ships.

---

## Security (V1)

### What V1 Does
- **LAN-only access** — no internet-facing ports, no tunneling
- **No authentication** — anyone on the LAN can view the dashboard
- **No encryption** — HTTP, not HTTPS (standard for factory LAN tools)
- **Write endpoints open** — `/api/plc/write-coil` has no auth gate

### Why This Is Acceptable for V1
Factory floor tools (HMIs, SCADA web UIs, PLC programming ports) universally operate on unauthenticated LANs. The Pi Factory sits at the same trust level as the PLC programming port itself.

### V2 Security Roadmap
- Basic auth or API key for write endpoints
- Optional mTLS for inter-cluster communication
- Rate limiting on write operations
- Audit log for write operations

---

## Cluster Integration (Future)

Pi Factory currently runs **standalone** — no connection to the FactoryLM cluster (ALPHA/BRAVO/CHARLIE).

### Current State
- Pi Factory is a self-contained appliance
- Data stays in-memory, no persistence
- No communication with cluster nodes

### Future Integration Path
1. **Register with cluster** — Pi Factory announces itself to ALPHA on boot
2. **Push tag data to Qdrant** — Stream PLC data to CHARLIE (192.168.1.12) for vector search
3. **Claim the PI slot** — Use the reserved 192.168.1.30 address in CLUSTER.md
4. **Accept commands from ALPHA** — Orchestrator can trigger scans, read data
5. **Feed the dataset** — Every tag change becomes training data for the maintenance LLM

---

## OTA Updates (Future)

### Current State
Manual update only:
```bash
ssh pi@pi-factory.local
cd ~/factorylm/services/plc-modbus
git pull
sudo systemctl restart pi-factory
```

### Future
- Systemd timer that runs `git pull` + `pip install` on a schedule
- Version check endpoint: `/api/version` with git SHA
- Watchdog that auto-restarts if the process dies (partially done via `Restart=on-failure`)

---

## What This PRD Does NOT Cover

| Topic | Covered By |
|-------|-----------|
| The `factorylm_plc` Python library | PRD-003 |
| Modbus register maps and `BasePLCClient` | PRD-003 |
| `FactoryIOMicro820`, `FactoryState`, error codes | PRD-005 |
| Factory I/O scene integration | PRD-005 |
| LLM4PLC structured text generation | PRD-005 |
| Voice HMI (speech-to-text, text-to-speech) | PRD-002 |
| Web dashboard with chat/history/analytics | PRD-004 |
| Core LLM abstraction layer | PRD-001 |

---

## Completion Criteria

### Already Done
- [x] FastAPI backend with discovery daemon (`backend/main.py`)
- [x] SSE streaming endpoint (`/api/stream`)
- [x] Static dashboard with live device cards (`backend/static/index.html`)
- [x] Modbus TCP subnet scanner (`backend/services/network_scanner.py`)
- [x] EtherNet/IP device discovery (`backend/services/discovery_daemon.py`)
- [x] Mock mode for hardware-free demo (`FACTORYLM_MOCK_MODE=true`)
- [x] Systemd service definition (`deploy/pi-factory.service`)
- [x] Avahi mDNS service (`deploy/avahi-pi-factory.service`)
- [x] Zero-config install script (`deploy/setup-pi-factory.sh`)
- [x] DHCP + link-local fallback network config
- [x] CORS enabled for cross-origin dashboard access

### Needs Testing on Real Pi Hardware
- [ ] `setup-pi-factory.sh` runs clean on fresh Ubuntu Server 24.04 LTS
- [ ] Systemd service starts on boot and stays running
- [ ] Avahi resolves `pi-factory.local` from other machines on LAN
- [ ] Link-local fallback works when no DHCP server present
- [ ] Discovery finds real PLCs on a factory subnet
- [ ] Dashboard renders correctly on mobile (phone on factory floor)
- [ ] Service recovers after network cable disconnect/reconnect
- [ ] Service survives Pi reboot (power cycle test)

### Not Yet Built
- [ ] OTA update mechanism
- [ ] Cluster registration (announce to ALPHA)
- [ ] Tag data push to Qdrant (CHARLIE)
- [ ] Write endpoint authentication
- [ ] Historical data persistence

---

## Success Criteria

```
FACTORYLM_PI_FACTORY_COMPLETE

Plug a Raspberry Pi into any factory Ethernet switch.
Within 60 seconds:
  1. Pi gets an IP (DHCP or 169.254.x.x link-local fallback)
  2. pi-factory.local resolves via mDNS
  3. http://pi-factory.local:8000 loads the dashboard
  4. Every Modbus TCP and EtherNet/IP PLC on the subnet appears
  5. Tag values update in real time

Proof:
  - Pi running headless with only Ethernet + power connected
  - Browser on a phone showing live PLC data
  - No configuration was performed after flashing the SD card
```

---

## Ralph Loop Instructions

```text
You are hardening the Pi Factory appliance for real factory deployment.

HOMEWORK PHASE:
1. Review PRD-003 (base PLC client) and PRD-005 (Factory I/O)
2. Read deploy/setup-pi-factory.sh — understand every step
3. Read backend/main.py and all routes — map the full API surface
4. Read backend/services/discovery_daemon.py — understand scan logic
5. Read backend/static/index.html — understand the dashboard
6. Document findings in HOMEWORK.md

DESIGN PHASE:
1. Plan the Pi hardware test (which Pi model, which network)
2. Identify failure modes (no DHCP, cable disconnect, PLC offline)
3. Plan mock-mode validation path (no hardware needed)
4. Document in DESIGN.md

EXECUTION PHASE:
1. Flash Ubuntu Server 24.04 LTS (64-bit) to SD card
2. Run setup-pi-factory.sh on the Pi
3. Verify each completion criteria checkbox
4. Test link-local fallback (disconnect from DHCP network)
5. Test mobile dashboard (phone on same LAN)
6. Test power cycle recovery (unplug Pi, plug back in)
7. Run mock mode on a dev machine to verify demo path
8. Document all results with timestamps and screenshots

CRITICAL:
- Do NOT add features — this PRD is about testing what exists
- Every checkbox must have deterministic proof (log output, screenshot, curl response)
- If setup-pi-factory.sh fails, fix the script, don't work around it
- Mock mode must work on macOS/Linux without any Pi hardware

When complete, append "FACTORYLM_PI_FACTORY_COMPLETE" to end of this PRD.
```

---

## Dependency Graph

```
PRD-001 (Core)
    │
    ├──→ PRD-002 (Voice HMI)
    │
    ├──→ PRD-003 (PLC Client)
    │       │
    │       ├──→ PRD-005 (Factory I/O)
    │       │
    │       └──→ PRD-006 (Pi Factory) ← THIS PRD
    │               │
    │               └──→ Uses PRD-003 library for Modbus
    │               └──→ Uses PRD-005 for Factory I/O scenes
    │
    └──→ PRD-004 (Dashboard — dev tool, separate from Pi Factory)
```

---

## Next Steps After This PRD

1. **Test on real Pi hardware** — Flash SD card, run install, validate all checkboxes
2. **Cluster integration** — Register Pi Factory with ALPHA, stream data to CHARLIE
3. **Edge Mode PRD** — If GPIO bridge proves useful, write PRD-007
4. **Security hardening** — Auth for write endpoints before multi-user deployment
5. **OTA updates** — Automated git pull + service restart on schedule

---

**BUILD AFTER PRD-003 + PRD-005. This is the first thing that ships to a factory floor.**
