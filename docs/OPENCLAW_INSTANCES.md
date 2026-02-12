# OpenClaw / ClawdBot Instance Map

**Last Updated:** 2026-02-12

Keep this file current. One source of truth for all bot instances.

---

## Instance Overview

| Instance | Codename | Bot | Host | Status |
|----------|----------|-----|------|--------|
| **Local** | `jarvis-local` | @TravelLaptop_bot | Windows laptop | ✅ Active |
| **DO VPS** | `ultron` | @UltronVPS_bot | DigitalOcean (100.68.120.99) | ⚠️ Billing issues |
| **Hostinger** | `jarvis-legacy` | _(unnamed bot)_ | Hostinger (72.60.175.144) | ⚠️ Decommissioning |

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
| **Primary model** | `groq/llama-3.3-70b-versatile` |
| **Fallbacks** | DeepSeek R1 → OpenRouter Llama → Gemini Flash → DeepSeek Chat |
| **Providers** | Groq, OpenRouter, Anthropic, Google |
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
| **Primary model** | `groq/llama-3.3-70b-versatile` |
| **Fallbacks** | DeepSeek R1 → Claude Sonnet → Gemini Flash |
| **Providers** | Groq, Ollama (qwen2.5:0.5b, tinyllama), Anthropic (OAuth) |
| **Extra features** | WhatsApp channel, TTS (edge), heartbeat every 2h |
| **Source code** | `https://github.com/Mikecranesync/clawdbot` (private) |
| **Identity** | Not yet named — uses extended SOUL.md with Jesus H Christ agent |

### ⚠️ Known Issues (as of 2026-02-12)
- Anthropic OAuth: rate-limited (Claude Code workspace)
- Google API: billing exhausted → top up at https://console.cloud.google.com/billing
- **Groq is working** ✅

---

## 3. `jarvis-legacy` — Hostinger VPS (Decommissioning)

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
```

---

## Provider Summary (All Instances)

| Provider | Local | DO VPS | Hostinger | Cost |
|----------|-------|--------|-----------|------|
| **Groq** | ✅ | ✅ | ✅ | Free tier |
| **OpenRouter** | ✅ | ❌ | ❌ | Pay-per-use |
| **Anthropic** | ✅ (API key) | ⚠️ (OAuth rate-limited) | ⚠️ (OAuth broken) | $$$ |
| **Google/Gemini** | ⚠️ (auth errors) | ⚠️ (billing exhausted) | ✅ (API key) | $ |
| **Ollama (local)** | ❌ | ✅ (qwen 0.5B, tinyllama) | ✅ (qwen 0.5B, tinyllama) | Free |

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

### Honeycomb (Distributed Tracing)

**Dashboard:** [ui.honeycomb.io](https://ui.honeycomb.io) → Datasets: `openclaw-ultron`, `openclaw-jarvis-legacy`, `openclaw-jarvis-local`

| Instance | Method | Service Name | Config |
|----------|--------|-------------|--------|
| `ultron` (DO) | OTel SDK via NODE_OPTIONS | `openclaw-ultron` | systemd env vars |
| `jarvis-legacy` (Hostinger) | OTel SDK via NODE_OPTIONS | `openclaw-jarvis-legacy` | systemd env vars |
| `jarvis-local` (Windows) | OTel SDK via NODE_OPTIONS | `openclaw-jarvis-local` | User env vars |

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
