# TRC-2026-03-01-001: CHARLIE Node Brought Online

| Field | Value |
|-------|-------|
| **ID** | TRC-2026-03-01-001 |
| **Date** | 2026-03-01 |
| **Author** | Claude (CHARLIE node) |
| **Duration** | 30 min |
| **Type** | infrastructure |
| **Services** | qdrant, ssh, network |
| **Devices** | CHARLIE (192.168.1.12) |
| **Trigger** | Bring CHARLIE node online as Vector KB for FactoryLM cluster |

---

## Context

CHARLIE (Mac Mini, Apple Silicon, 16GB RAM, 157GB free) was bootstrapped via the factorylm bootstrap script but had no cluster services running. The Thunderbolt Ethernet port had a direct cable to Bravo but was on link-local only. WiFi provided internet access.

## What Was Done

### 1. Network Configuration
- Set static IP 192.168.1.12/24 on en0 (Ethernet) — **no gateway** (direct cable, no router)
- Fixed routing: Ethernet had a bogus gateway (192.168.1.1) which hijacked the default route from WiFi. Removed gateway so internet routes through WiFi (en1 → 192.168.4.1) and cluster LAN stays on en0
- WiFi stays on DHCP (192.168.4.110) for internet access

### 2. Qdrant v1.17.0 Installed
- Binary at `~/bin/qdrant` (aarch64-apple-darwin)
- Config at `~/qdrant-data/config.yaml` (HTTP :8000, gRPC :6334)
- Start script at `~/bin/start-qdrant.sh`
- Verified: `curl http://localhost:8000/collections` returns `{"status":"ok"}`

### 3. Bun v1.3.10 Installed
- Installed via `bun.sh` installer
- Available at `~/.bun/bin/bun`

### 4. SSH Enabled
- Remote Login enabled via System Settings > General > Sharing
- Port 22 verified listening

### 5. Xcode CLT Installed
- git v2.50.1 now available
- Python3 and other dev tools working

### 6. Bravo (192.168.1.11) Configured Remotely
- Bravo was headless, reachable only at link-local 169.254.160.217
- Used `expect` to SSH in as `bravonode` and set static IP 192.168.1.11/24
- Installed CHARLIE's SSH key for passwordless access
- Verified: Ollama running on :11434 with mistral:7b and llama3.1:8b loaded

### 7. Cluster Start Script
- Created `~/bin/start-cluster.sh` — starts Qdrant, checks all cluster nodes, prints status
- All checks passing (except Bravo was initially unreachable, now fixed)

## Final Cluster Status

| Node | IP | Status |
|------|-----|--------|
| Alpha | 192.168.1.10 | Reachable |
| Bravo | 192.168.1.11 | Reachable — Ollama running, mistral:7b + llama3.1:8b |
| CHARLIE | 192.168.1.12 | Online — Qdrant :8000, SSH, Bun, gh CLI |
| PLC | 192.168.1.100 | Reachable |

## Files Created (on CHARLIE, outside repo)

| File | Purpose |
|------|---------|
| `~/bin/qdrant` | Qdrant v1.17.0 binary |
| `~/bin/start-qdrant.sh` | Qdrant launcher |
| `~/bin/start-cluster.sh` | Full CHARLIE node startup script |
| `~/qdrant-data/config.yaml` | Qdrant config (port 8000) |
| `~/.ssh/id_ed25519` | SSH key (public key deployed to Bravo) |

## Mistakes

### AI Mistakes
- Initially set Ethernet gateway to 192.168.1.1 (in a prior session), which broke internet routing. Fixed by removing gateway.

### Human Mistakes
- None this session.

## Queryable Tags

- **node**: CHARLIE
- **services**: qdrant, ssh
- **ports**: 8000 (qdrant), 6334 (grpc), 22 (ssh)
- **network**: 192.168.1.12 (en0), 192.168.4.110 (en1/wifi)
