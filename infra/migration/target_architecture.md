# Target Architecture — Offline-First with Minimal VPS

**Last Updated:** 2026-02-13  
**Author:** Mike  
**Status:** Planned — not yet implemented

---

## End-State Vision

Everything runs locally. The only cloud resource is one tiny VPS for public-facing traffic.

### Local (laptop / home lab) — runs EVERYTHING

| Service | Stack | Notes |
|---------|-------|-------|
| Matrix backend | FastAPI + Postgres | Core API for FactoryLM |
| FactoryLM core | Python | LLM abstraction, knowledge base |
| PLC simulator | Python | Simulates Micro 820 Modbus registers |
| Cosmos client stub | Python | Stub for future Cosmos agent |
| Web dashboard | React / TypeScript | HMI for technicians |
| Telegram bot | Python | PLC copilot, photo→diagnosis |
| Chat client | TBD | Alternative HMI |
| OpenClaw bot | Node.js | Local instance (@TravelLaptop_bot) |
| Observability | Honeycomb + optional Axiom | Traces and logs |
| Ollama | Local LLM | qwen2.5, tinyllama, etc. |

### One Minimal VPS (Hetzner) — only for public-facing traffic

| Service | Purpose |
|---------|---------|
| Caddy | Reverse proxy, automatic HTTPS, simple config |
| Telegram webhook endpoint | Receives Telegram updates, forwards to local via Tailscale |
| Optional: Cloudflare Tunnel | Alternative to Tailscale for webhook forwarding |
| Optional: WireGuard | Alternative VPN back to local |
| Optional: tiny Postgres | For public demo only |

**NO background agents, NO heavy services on the VPS.**

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│  Local Machine (Windows 11)                             │
│                                                         │
│  ┌─────────────────────────────────────────────────┐    │
│  │  Docker Compose (or bare-metal)                 │    │
│  │                                                 │    │
│  │  ┌──────────────┐  ┌──────────────────────┐     │    │
│  │  │  Postgres     │  │  Matrix API (FastAPI)│     │    │
│  │  └──────────────┘  └──────────────────────┘     │    │
│  │                                                 │    │
│  │  ┌──────────────┐  ┌──────────────────────┐     │    │
│  │  │ PLC Simulator │  │  Cosmos Agent (stub) │     │    │
│  │  └──────────────┘  └──────────────────────┘     │    │
│  │                                                 │    │
│  │  ┌──────────────┐  ┌──────────────────────┐     │    │
│  │  │ HMIs (web,   │  │  OpenClaw Bot         │     │    │
│  │  │  chat)       │  │  (Telegram gateway)  │     │    │
│  │  └──────────────┘  └──────────────────────┘     │    │
│  │                                                 │    │
│  │  ┌──────────────┐  ┌──────────────────────┐     │    │
│  │  │ Ollama       │  │  Observability        │     │    │
│  │  │ (local LLM)  │  │  (Honeycomb + Axiom) │     │    │
│  │  └──────────────┘  └──────────────────────┘     │    │
│  └─────────────────────────────────────────────────┘    │
│                                                         │
│         │  Tailscale mesh (encrypted WireGuard)         │
└─────────┼───────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────┐
│  Hetzner VPS (minimal)                                  │
│                                                         │
│  ┌──────────────────────────────────────────────┐       │
│  │  Caddy (reverse proxy, auto-HTTPS)           │       │
│  │    ├── Telegram webhook → forward to local   │       │
│  │    └── Optional: public demo endpoints       │       │
│  └──────────────────────────────────────────────┘       │
│                                                         │
│  ┌──────────────────────────────────────────────┐       │
│  │  Optional: Cloudflare Tunnel (alt to Tailscale) │    │
│  └──────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────┘
```

---

## Why Offline-First

| Reason | Explanation |
|--------|-------------|
| **Faster iteration** | No deploy cycle — change code, restart, test immediately |
| **Works without internet** | Develop and demo on a plane, at a factory, anywhere |
| **Cheaper** | No VPS bills beyond one ~$5/mo instance |
| **Security** | Data stays on your machine — no cloud exposure |
| **Layer 0 alignment** | Matches FactoryLM's philosophy: intelligence flows downward, less cloud over time |

---

## Migration Order

| Step | Task | Depends On | Status |
|------|------|------------|--------|
| 1 | Inventory all VPS instances | — | ✅ Done (`infra/migration/vps_inventory.md`) |
| 2 | Extract configs/data from Hostinger | Step 1 | Not started |
| 3 | Extract configs/data from DigitalOcean | Step 1 | Not started |
| 4 | Set up local Docker Compose | Steps 2–3 | Not started |
| 5 | Configure Hetzner as minimal reverse proxy | Step 4 | Not started |
| 6 | Verify all services run locally | Steps 4–5 | Not started |
| 7 | Decommission Hostinger | Step 6 | Not started |
| 8 | Decommission DigitalOcean | Steps 6–7 (after Hetzner proves stable) | Not started |
