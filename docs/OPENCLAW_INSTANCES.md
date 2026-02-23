# OpenClaw / ClawdBot Instance Map

**Last Updated:** 2026-02-23

Keep this file current. One source of truth for all bot instances.

---

## Instance Overview

| Instance | Codename | Bot | Host | Status |
|----------|----------|-----|------|--------|
| **Local** | `jarvis-local` | @TravelLaptop_bot | Windows laptop | ✅ Active |
| **DO VPS** | `ultron` | @UltronVPS_bot | DigitalOcean (100.68.120.99) | ✅ Fixed (Anthropic primary) |
| **Hetzner** | `hetzner` | _(pending migration)_ | Hetzner (46.225.103.156) | 🟡 Fresh — needs setup |
| **Hostinger** | `jarvis-legacy` | _(unnamed bot)_ | Hostinger (72.60.175.144) | ⚠️ Decommissioning |
| **Mac Mini** | `oc_macaroni` | @Tony_Macaroni_bot | Mac Mini "Macaroni" (Tailscale) | 🟡 New — pending first boot |

---

## 1. `jarvis-local` — Local Windows Laptop

| Detail | Value |
|--------|-------|
| **Bot** | @TravelLaptop_bot |
| **Machine** | Mike's Windows 11 laptop |
| **Config** | `C:\Users\hharp\.openclaw\openclaw.json` |
| **Workspace** | `C:\Users\hharp\.openclaw\workspace\` |
| **SOUL.md** | `C:\Users\hharp\.openclaw\workspace\SOUL.md` |
| **IDENTITY.md** | `C:\Users\hharp\.openclaw\workspace\IDENTITY.md` |
| **Agent data** | `C:\Users\hharp\.openclaw\agents\main\agent\` |
| **Models.json** | `C:\Users\hharp\.openclaw\agents\main\agent\models.json` |
| **Gateway port** | 18800 |
| **Primary model** | `anthropic/claude-opus-4-5-20250514` |
| **Fallbacks** | groq/llama-3.3-70b-versatile → openrouter/llama-3.3-70b → openrouter/deepseek-chat → gemini-2.5-flash |
| **Compaction** | `safeguard` + `reserveTokensFloor: 4000` |
| **Providers** | Anthropic, Groq, OpenRouter, Google |
| **Source code** | `https://github.com/Mikecranesync/clawdbot` (private) |
| **Identity** | Jarvis — sharp, competent ops assistant |

---

## 2. `ultron` — DigitalOcean VPS

| Detail | Value |
|--------|-------|
| **Bot** | @UltronVPS_bot |
| **Machine** | DigitalOcean droplet |
| **SSH** | `ssh root@100.68.120.99` (via Tailscale) |
| **Config** | `/root/.openclaw/openclaw.json` |
| **Workspace** | `/root/jarvis-workspace/` |
| **SOUL.md** | `/root/jarvis-workspace/SOUL.md` |
| **IDENTITY.md** | `/root/jarvis-workspace/IDENTITY.md` (blank template) |
| **Agent data** | `/root/.openclaw/agents/main/agent/` |
| **Models.json** | `/root/.openclaw/agents/main/agent/models.json` |
| **Service** | `systemctl status openclaw` |
| **Logs** | `/tmp/openclaw/openclaw-YYYY-MM-DD.log` |
| **Gateway port** | 18789 |
| **Primary model** | `anthropic/claude-sonnet-4-20250514` |
| **Fallbacks** | groq/llama-3.1-8b-instant → groq/llama-3.3-70b-versatile → google/gemini-2.5-flash |
| **Compaction** | `safeguard` + `reserveTokensFloor: 4000` |
| **Providers** | Anthropic (OAuth, 280d token), Groq, Google, Ollama (qwen2.5:0.5b, tinyllama) |
| **Extra features** | WhatsApp channel, TTS (edge), heartbeat every 2h |
| **Source code** | `https://github.com/Mikecranesync/clawdbot` (private) |
| **Identity** | Not yet named — uses extended SOUL.md with Jesus H Christ agent |

### ✅ Fix Applied (2026-02-12 ~23:00 UTC)
- Switched primary from Groq → Anthropic Claude Sonnet 4 (OAuth token valid 280 days)
- Root cause: Groq TPM limit (12K) too low for 18K system prompt
- Fixed invalid fallback `groq/qwen/qwen3-32b` → `groq/llama-3.1-8b-instant`
- Google API billing still exhausted (kept as last fallback)
- **Bot is now responding** ✅

---

## 3. `hetzner` — Hetzner VPS (New — Pending Setup)

| Detail | Value |
|--------|-------|
| **Bot** | _(pending — will take over @UltronVPS_bot)_ |
| **Machine** | Hetzner Cloud |
| **IPv4** | `46.225.103.156` |
| **IPv6** | `2a01:4f8:1c19:966::/64` |
| **SSH** | `ssh root@46.225.103.156` |
| **Status** | 🟡 Fresh server — needs Node 22, pnpm, clawdbot, systemd |

### Setup Checklist
- [ ] Change root password & add SSH key
- [ ] Install Node 22 + pnpm
- [ ] Install Tailscale
- [ ] Clone clawdbot repo
- [ ] Deploy with `clawdbot daemon install`
- [ ] Migrate config from DO ultron instance
- [ ] Configure Honeycomb tracing
- [ ] Configure Vector/Axiom log shipping
- [ ] Verify bot responds
- [ ] Decommission DigitalOcean VPS

---

## 4. `jarvis-legacy` — Hostinger VPS (Decommissioning)

| Detail | Value |
|--------|-------|
| **Bot** | _(separate bot token)_ |
| **Machine** | Hostinger VPS |
| **SSH** | `ssh root@72.60.175.144` or `ssh hostinger` |
| **Config** | `/root/.clawdbot/clawdbot.json` |
| **Workspace** | `/root/jarvis-workspace/` |
| **SOUL.md** | `/root/jarvis-workspace/SOUL.md` (extended version with monorepo laws) |
| **Agent data** | `/root/.clawdbot/agents/main/agent/` |
| **Gateway port** | 18789 |
| **Primary model** | `groq/llama-3.3-70b-versatile` (just added) |
| **Fallbacks** | DeepSeek R1 → Claude Sonnet → Gemini Flash |
| **Providers** | Groq (just added), Ollama, Anthropic (OAuth - broken) |
| **Source code** | `https://github.com/Mikecranesync/clawdbot` (private) |
| **Also has** | Rivet-PRO at `/root/Rivet-PRO/` with Jesus H Christ agent |
| **Status** | Being decommissioned — migrate anything useful to DO VPS |

---

## 5. `oc_macaroni` — Mac Mini "Macaroni" (Home Base)

| Detail | Value |
|--------|-------|
| **Bot** | @Tony_Macaroni_bot |
| **Machine** | Mac Mini (Apple Silicon) — always-on home base |
| **Hostname** | `macaroni` |
| **Tailscale IP** | _(pending first boot — will be 100.x.x.x)_ |
| **Config** | `/Users/Macaroni/.openclaw/openclaw.json` |
| **Workspace** | `/Users/Macaroni/openclaw-workspace/` |
| **Agent data** | `/Users/Macaroni/.openclaw/agents/main/agent/` |
| **Gateway port** | 18789 |
| **Bind** | `0.0.0.0` (reachable from Tailscale mesh) |
| **Primary model** | `anthropic/claude-sonnet-4-20250514` |
| **Fallbacks** | groq/llama-3.1-8b-instant → groq/llama-3.3-70b-versatile → google/gemini-2.5-flash |
| **Compaction** | `safeguard` + `reserveTokensFloor: 4000` |
| **Providers** | Anthropic (API key), Groq |
| **Heartbeat** | Every 2h to Telegram `8445149012` |
| **Auto-start** | launchd (`~/Library/LaunchAgents/ai.openclaw.gateway.plist`) |
| **Logs** | `/tmp/openclaw/openclaw-stdout.log`, `/tmp/openclaw/openclaw-stderr.log` |
| **Source code** | `https://github.com/Mikecranesync/clawdbot` (private) |
| **Identity** | Tony Macaroni — TBD during first conversation |
| **Setup guide** | See `openclaw-mac-mini-setup.md` gist |

### Status
- 🟡 Pending first boot — machine has never been turned on
- Setup guide created, config templated from `ultron` instance
- Also hosts Mike's Brain (`~/mikes-brain/`) — knowledge graph v0.1.0

---

## SOUL.md Locations & Differences

| Instance | SOUL.md Flavor |
|----------|---------------|
| `jarvis-local` | Minimal ops-focused (SSH access, Telegram concise, status emojis) |
| `ultron` | Full version (AI Engineering OS, Output Format Law, Jesus H Christ ref) |
| `jarvis-legacy` | Extended (all of ultron + Monorepo & Versioning Law + inline Jesus section) |

### Recommendation
Consolidate to one canonical SOUL.md and sync across instances.
The `ultron` version is the most complete and balanced.

---

## Quick Commands

```bash
# Local — restart OpenClaw
# (run from PowerShell)
openclaw gateway

# DO VPS — check status
ssh vps "systemctl status openclaw"

# DO VPS — restart
ssh vps "systemctl restart openclaw"

# DO VPS — tail logs
ssh vps "tail -f /tmp/openclaw/openclaw-$(date +%Y-%m-%d).log"

# Hostinger — check status
ssh hostinger "systemctl status clawdbot 2>/dev/null || ps aux | grep claw"

# Mac Mini — check status (via Tailscale)
ssh Macaroni@<macaroni-tailscale-ip> "launchctl list | grep openclaw"

# Mac Mini — tail logs
ssh Macaroni@<macaroni-tailscale-ip> "tail -f /tmp/openclaw/openclaw-stdout.log"

# Mac Mini — health check
curl http://<macaroni-tailscale-ip>:18789/health
```

---

## Provider Summary (All Instances)

| Provider | Local | DO VPS | Hostinger | Mac Mini | Cost |
|----------|-------|--------|-----------|----------|------|
| **Groq** | ✅ | ✅ | ✅ | ✅ | Free tier |
| **OpenRouter** | ✅ | ❌ | ❌ | ❌ | Pay-per-use |
| **Anthropic** | ✅ (API key) | ⚠️ (OAuth rate-limited) | ⚠️ (OAuth broken) | ✅ (API key) | $$$ |
| **Google/Gemini** | ⚠️ (auth errors) | ⚠️ (billing exhausted) | ✅ (API key) | 🟡 (fallback only) | $ |
| **Ollama (local)** | ❌ | ✅ (qwen 0.5B, tinyllama) | ✅ (qwen 0.5B, tinyllama) | ❌ | Free |

---

---

## Observability

### Axiom (Log Aggregation)

**Dashboard:** [app.axiom.co](https://app.axiom.co) → Dataset: `openclaw-logs`

| Instance | Shipper | Status | Config |
|----------|---------|--------|--------|
| `ultron` (DO) | Vector systemd | ✅ Running | `/etc/vector/vector.yaml` |
| `jarvis-legacy` (Hostinger) | Vector systemd | ✅ Running | `/etc/vector/vector.yaml` |
| `jarvis-local` (Windows) | PowerShell script | Manual | `~\.openclaw\axiom-shipper.ps1` |
| `oc_macaroni` (Mac Mini) | _(not configured)_ | 🟡 Pending | — |

### Honeycomb (Distributed Tracing)

**Dashboard:** [ui.honeycomb.io](https://ui.honeycomb.io) → Datasets: `openclaw-ultron`, `openclaw-jarvis-legacy`, `openclaw-jarvis-local`

| Instance | Method | Service Name | Config |
|----------|--------|-------------|--------|
| `ultron` (DO) | OTel SDK via NODE_OPTIONS | `openclaw-ultron` | systemd env vars |
| `jarvis-legacy` (Hostinger) | OTel SDK via NODE_OPTIONS | `openclaw-jarvis-legacy` | systemd env vars |
| `jarvis-local` (Windows) | OTel SDK via NODE_OPTIONS | `openclaw-jarvis-local` | User env vars |
| `oc_macaroni` (Mac Mini) | _(not configured)_ | `openclaw-macaroni` | — |

- **Free tier**: 20M events/month
- **Setup scripts**: `scripts/honeycomb/` in FactoryLM repo
- **Bootstrap file**: `tracing.js` loaded via `NODE_OPTIONS=-r /path/to/tracing.js`
- Uses vanilla OpenTelemetry SDK (not Honeycomb's archived distro)

### Axiom vs Honeycomb

| Concern | Axiom | Honeycomb |
|---------|-------|-----------|
| **What** | Logs (stdout/stderr) | Distributed traces (spans) |
| **How** | Vector log shipper | OTel SDK in-process |
| **Best for** | Log search, text alerts | Latency analysis, error waterfalls, dependency maps |

### Quick Commands

```powershell
# Start local Axiom shipper
$env:AXIOM_TOKEN = "$AXIOM_TOKEN"  # Real token in Doppler — do not hardcode
powershell -File "$env:USERPROFILE\.openclaw\axiom-shipper.ps1"
```

```bash
# Check VPS shippers
ssh vps "systemctl status vector"
ssh hostinger "systemctl status vector"
```

---

*All instances run the same codebase: https://github.com/Mikecranesync/clawdbot*
*Config differs per instance. This doc is the map.*
