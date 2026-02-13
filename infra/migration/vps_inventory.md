# VPS Inventory

**Last Updated:** 2026-02-13  
**Author:** Mike  
**Status:** Active — source of truth for all infrastructure

---

## Summary

| # | Codename | Provider | IPv4 | Purpose | Status | Migration Priority |
|---|----------|----------|------|---------|--------|--------------------|
| 1 | ultron | DigitalOcean | 100.68.120.99 (Tailscale) | OpenClaw bot, Jarvis workspace | Active | High |
| 2 | jarvis-legacy | Hostinger | 72.60.175.144 | Legacy clawdbot, Rivet-PRO | Decommissioning | High |
| 3 | hetzner | Hetzner Cloud | 46.225.103.156 | Replacement VPS (pending setup) | Fresh | Medium |
| — | local | — | — | Dev laptop, local OpenClaw, FactoryLM dev | Active | Low |

---

## VPS 1: DigitalOcean ("ultron")

| Field | Value |
|-------|-------|
| **Hostname/Codename** | ultron |
| **Provider** | DigitalOcean |
| **IPv4** | Accessible via Tailscale at `100.68.120.99` |
| **SSH** | `ssh root@100.68.120.99` |
| **Purpose** | OpenClaw bot (@UltronVPS_bot), Jarvis workspace |
| **Status** | Active, fixed 2026-02-12 (Anthropic primary, Groq fallback) |
| **Plan** | Migrate to Hetzner, then decommission |

### Running Services

| Service | Type | Notes |
|---------|------|-------|
| `openclaw` | systemd | Telegram bot (Node.js, clawdbot codebase) |
| Vector | log shipper | Shipping to Axiom |
| OTel tracing | tracing | Shipping to Honeycomb |
| Ollama | local LLM | Models: `qwen2.5:0.5b`, `tinyllama` |

### Databases

None — uses external APIs only.

### Important Data Paths

| Path | Contents |
|------|----------|
| `/root/.openclaw/openclaw.json` | OpenClaw config |
| `/root/.openclaw/agents/main/agent/` | Agent data |
| `/root/.openclaw/agents/main/agent/models.json` | Model config |
| `/root/jarvis-workspace/` | Jarvis workspace |
| `/root/jarvis-workspace/SOUL.md` | SOUL.md |
| `/tmp/openclaw/openclaw-YYYY-MM-DD.log` | Logs (daily rotation) |
| `/etc/vector/vector.yaml` | Vector config |

---

## VPS 2: Hostinger ("jarvis-legacy")

| Field | Value |
|-------|-------|
| **Hostname/Codename** | jarvis-legacy |
| **Provider** | Hostinger |
| **IPv4** | `72.60.175.144` |
| **SSH** | `ssh root@72.60.175.144` or `ssh hostinger` |
| **Purpose** | Legacy clawdbot instance, also has Rivet-PRO |
| **Status** | Decommissioning — migrate useful data |
| **Plan** | Extract configs/workspace, then shut down |

### Running Services

| Service | Type | Notes |
|---------|------|-------|
| `clawdbot` | systemd | Older bot variant |
| Vector | log shipper | Shipping to Axiom |
| OTel tracing | tracing | Shipping to Honeycomb |
| Ollama | local LLM | Models: `qwen2.5:0.5b`, `tinyllama` |

### Databases

None.

### Important Data Paths

| Path | Contents |
|------|----------|
| `/root/.clawdbot/clawdbot.json` | Clawdbot config |
| `/root/.clawdbot/agents/main/agent/` | Agent data |
| `/root/jarvis-workspace/` | Jarvis workspace |
| `/root/Rivet-PRO/` | Rivet-PRO project |

---

## VPS 3: Hetzner ("hetzner")

| Field | Value |
|-------|-------|
| **Hostname/Codename** | hetzner |
| **Provider** | Hetzner Cloud |
| **IPv4** | `46.225.103.156` |
| **IPv6** | `2a01:4f8:1c19:966::/64` |
| **SSH** | `ssh root@46.225.103.156` |
| **Purpose** | Replacement for DO + Hostinger (pending setup) |
| **Status** | Fresh — needs Node 22, pnpm, Tailscale, clawdbot |
| **Plan** | This becomes the ONE minimal VPS (reverse proxy + public endpoint) |

### Running Services

None yet (fresh server).

### Databases

None.

### Important Data Paths

N/A — not yet provisioned.

---

## Local Machine

| Field | Value |
|-------|-------|
| **Machine** | Mike's Windows 11 laptop |
| **Purpose** | Development, local OpenClaw (@TravelLaptop_bot), FactoryLM dev |

### Running Services (manual start)

| Service | Notes |
|---------|-------|
| OpenClaw gateway | Local Telegram bot instance |
| My-Ralph API | FastAPI dev server |
| PLC Modbus API | When PLC is on network |

### Important Paths

| Path | Contents |
|------|----------|
| `C:\Users\hharp\.openclaw\openclaw.json` | OpenClaw config (local) |
| `C:\Users\hharp\OneDrive\Desktop\FactoryLM` | FactoryLM monorepo |
