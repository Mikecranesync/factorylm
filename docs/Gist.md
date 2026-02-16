# FactoryLM — The One-Pager

*Last updated: 2026-02-12*

---

## What Is It?

FactoryLM helps **factory technicians** figure out what's wrong with their machines — faster, cheaper, and without needing an expert on-site.

**How it works:**
1. A technician takes a photo of a broken machine or types a question (via WhatsApp, Telegram, or a web app).
2. The system looks up the answer in a knowledge base of manuals, fault codes, and past fixes.
3. If it doesn't know the answer, it asks an AI model (like Claude or Llama).
4. Over time, AI answers get turned into code so the same question never needs AI again.

**It never controls equipment.** Read-only diagnostics only. This makes it safe and easy to approve.

---

## Who Built It?

**Mike Harper** — solo founder, industrial automation + AI engineering background.

---

## What's Working Today?

| What | Status | What It Does |
|------|--------|-------------|
| **LLM Core** (`core/`) | ✅ Production | Talks to Groq, Claude, and DeepSeek. 148 tests. |
| **PLC Client** (`services/plc-modbus/`) | ✅ Working | Reads data from Allen-Bradley PLCs via Modbus. 162 tests. |
| **Photo Bot** (`services/plc-copilot/`) | ✅ Working | Telegram bot: send a photo of equipment → get a CMMS work order. Uses Google Gemini Vision. |
| **My-Ralph** (`My-Ralph/`) | ✅ Production | Autonomous AI dev loop tool. 321 tests. |
| **CMMS App** (`apps/cmms/`) | ⚠️ Forked | Maintenance management web app (Java + React). Not yet rebranded. |
| **OpenClaw Bots** (separate repo) | ✅ Running | 3 Telegram bots on different servers, all AI-powered. |

---

## The Big Idea

**Use less AI over time, not more.**

```
Day 1:   "Why is motor 7 vibrating?"  →  Ask Claude  →  $0.05, 2 seconds
Day 30:  Same question  →  Pattern recognized  →  Workflow created
Day 60:  Same question  →  Code runs instantly  →  $0.00, 0.1 seconds
```

FactoryLM has 4 layers of intelligence. The goal is to push everything to Layer 0 (instant, free, no AI):

| Layer | What | Speed | Cost |
|-------|------|-------|------|
| **0** | Knowledge base + code | <100ms | Free |
| **1** | Tiny AI on a Raspberry Pi | ~1s | Free |
| **2** | Big AI on a local GPU | ~3s | Electricity |
| **3** | Cloud AI (Claude, etc.) | ~2s | $$$ |

---

## How Is It Built?

**Monorepo** (one repo, many projects) using Turborepo:

```
FactoryLM/
├── core/             ← Python LLM library (the brain)
├── services/
│   ├── plc-modbus/   ← Talks to factory PLCs
│   └── plc-copilot/  ← Telegram photo bot
├── apps/
│   └── cmms/         ← Maintenance management app
├── My-Ralph/         ← AI dev loop tool
├── scripts/          ← Utility scripts, Honeycomb setup
└── docs/             ← Architecture, config, observability guides
```

**Languages:** Python (most things), Bash (My-Ralph), Java + TypeScript (CMMS app).

**External services:** Groq (free LLM), Anthropic Claude, Google Gemini, Telegram, Axiom (logs), Honeycomb (traces), Doppler (secrets).

---

## How Do I Set It Up?

### Quick start (just the Python core):
```bash
cd core
pip install -e ".[dev]"
export GROQ_API_KEY="your-key-from-console.groq.com"
pytest                    # 148 tests should pass
```

### PLC service:
```bash
cd services/plc-modbus
pip install -e ".[dev]"
pytest                    # 162 tests should pass
```

### Photo bot:
```bash
cd services/plc-copilot
pip install -r requirements.txt
# Set env vars: TELEGRAM_BOT_TOKEN, GEMINI_API_KEY, CMMS_EMAIL, CMMS_PASSWORD
python photo_to_cmms_bot.py
```

### Secrets:
All API keys live in **Doppler** (not in code). See `docs/Config.md` for the full list.

---

## Key Contacts & Links

| What | Where |
|------|-------|
| Source code | https://github.com/Mikecranesync/factorylm |
| OpenClaw bots | https://github.com/Mikecranesync/clawdbot (private) |
| Honeycomb traces | https://ui.honeycomb.io |
| Axiom logs | https://app.axiom.co |
| Groq console | https://console.groq.com |
| Doppler secrets | https://dashboard.doppler.com |

---

## Glossary

| Term | Meaning |
|------|---------|
| **PLC** | Programmable Logic Controller — the computer that runs factory equipment |
| **Modbus** | Communication protocol for talking to PLCs |
| **CMMS** | Computerized Maintenance Management System — tracks work orders and assets |
| **VFD** | Variable Frequency Drive — controls motor speed |
| **OTel** | OpenTelemetry — standard for distributed tracing |
| **Doppler** | Secret management service (replaces .env files) |
| **OpenClaw** | Mike's Telegram bot framework (runs the AI assistants) |
| **My-Ralph** | Autonomous dev loop — runs Claude Code in a loop to build software |

---

*This document is for anyone new to the project. For the full technical vision, read [README.md](../README.md). For the full architecture, read [docs/Architecture.md](Architecture.md).*
