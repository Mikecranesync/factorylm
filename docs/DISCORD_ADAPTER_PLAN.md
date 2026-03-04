# Discord Adapter Plan — OpenClaw + Cosmos Cookoff Community

**Created:** 2026-02-17  
**Status:** PLAN — Awaiting Mike's approval  
**Goal:** Get OpenClaw into the NVIDIA Cosmos Cookoff Discord as Mike's presence — posting research, collaborating, and promoting FactoryLM before the Feb 26 deadline.

---

## Why Discord

- The **Cosmos Cookoff community lives on Discord** (invite: discord.com/invite/nvidiaomniverse)
- Judges and NVIDIA staff are active there — visibility matters
- Other contestants share progress, get feedback, form collaborations
- Being present and helpful = free advertising for FactoryLM

---

## Phase 1: Get Cosmos Model Access (TODAY)

1. **Go to [build.nvidia.com/nvidia/cosmos-reason2-8b](https://build.nvidia.com/nvidia/cosmos-reason2-8b)**
2. Click **"Get API Key"** — generate a new key scoped to this model
3. Test with the playground on that page (upload a video, ask a question)
4. If it works, add the new key to Doppler:
   ```bash
   doppler secrets set NVIDIA_COSMOS_API_KEY "nvapi-NEW-KEY" --project factorylm --config dev
   ```
5. If 404 persists, post in **#questions** on the Cookoff Discord:
   > "I'm building FactoryLM for the Cookoff. Have an NVIDIA API key but cosmos-reason2-8b returns 404 via the NIM API. Do I need a separate key from build.nvidia.com? Or is the model only available via self-hosting?"

---

## Phase 2: Discord Bot Setup (2-3 hours)

### Architecture

OpenClaw (clawdbot) already supports multiple channels. Discord would be a new adapter alongside Telegram and WhatsApp.

```
┌─────────────────────────────────────────────────┐
│  OpenClaw Gateway (:18800)                       │
│                                                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐    │
│  │ Telegram  │  │ WhatsApp │  │  Discord     │    │
│  │ Adapter   │  │ Adapter  │  │  Adapter     │    │
│  │ (built-in)│  │ (Baileys)│  │  (discord.js)│    │
│  └──────────┘  └──────────┘  └──────────────┘    │
│        │              │              │             │
│        └──────────────┼──────────────┘             │
│                       ▼                            │
│              ┌─────────────────┐                   │
│              │  LLM Router     │                   │
│              │  (Jarvis brain) │                   │
│              └─────────────────┘                   │
└─────────────────────────────────────────────────┘
```

### Option A: Standalone Discord Bot (FASTEST — Recommended)

A lightweight Python bot using `discord.py` that connects to the OpenClaw gateway API as a message forwarder. Runs as a separate process.

**File:** `services/discord-adapter/bot.py`

```python
# Skeleton — NOT final code
import discord
import httpx
import os

GATEWAY_URL = os.getenv("OPENCLAW_GATEWAY_URL", "http://localhost:18800")
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_message(message):
    if message.author == client.user:
        return
    # Forward to OpenClaw gateway, get response, reply
    async with httpx.AsyncClient() as http:
        resp = await http.post(f"{GATEWAY_URL}/api/message", json={
            "channel": "discord",
            "user_id": str(message.author.id),
            "text": message.content,
            "channel_id": str(message.channel.id),
        })
        reply = resp.json().get("reply", "")
    if reply:
        await message.reply(reply)

client.run(DISCORD_TOKEN)
```

### Option B: Native Clawdbot Channel (Longer)

Submit a PR to the clawdbot repo adding `discord.js` as a native channel. More integrated but takes longer.

**Recommendation:** Start with Option A. Migrate to native later.

---

## Phase 3: Discord Bot Registration (30 min)

1. Go to **[discord.com/developers/applications](https://discord.com/developers/applications)**
2. Create application: **"FactoryLM"**
3. Bot tab → Create Bot → Copy token
4. Enable intents:
   - ✅ MESSAGE CONTENT INTENT
   - ✅ SERVER MEMBERS INTENT  
   - ✅ PRESENCE INTENT
5. OAuth2 → URL Generator:
   - Scopes: `bot`, `applications.commands`
   - Permissions: `Send Messages`, `Read Message History`, `Embed Links`, `Attach Files`, `Add Reactions`
6. Use generated URL to invite bot to the **NVIDIA Omniverse Discord** (Cosmos Cookoff channels)
7. Store token in Doppler:
   ```bash
   doppler secrets set DISCORD_BOT_TOKEN "your-token" --project factorylm --config dev
   ```

---

## Phase 4: Community Engagement Strategy (Pre-Cookoff)

### What to Post (as Mike, via the bot)

| Type | Channel | Example | Frequency |
|------|---------|---------|-----------|
| **Progress updates** | #show-and-tell / #cosmos-cookoff | "Day 8: Got PLC→Cosmos Reason 2 pipeline working. Here's a 30s clip of fault detection →" | Every 2-3 days |
| **Technical questions** | #questions | "Anyone using Cosmos Reason 2 for industrial video? Curious about optimal video segment length for fault analysis" | As needed |
| **Help others** | #questions | Answer other contestants' questions about PLC integration, industrial AI, video analysis | Daily scan |
| **Architecture shares** | #show-and-tell | Share the network maps gist, architecture diagrams | Once |
| **Demo teaser** | #cosmos-cookoff | "Preview: FactoryLM detects a conveyor jam via PLC tags + video, Cosmos Reason 2 explains root cause in <5s" | Week of submission |
| **Collab offers** | #find-a-team | "Industrial AI builder here — happy to help anyone needing PLC/Modbus expertise for their Cookoff project" | Once |

### Tone & Rules

- **Be Mike** — authentic, technical, helpful, not salesy
- **Show don't tell** — screenshots, short clips, architecture diagrams over walls of text
- **Help first, promote second** — answering questions builds more credibility than self-promotion
- **Never spam** — quality over quantity, 1-2 posts per day max
- **Always disclose** if the bot is posting autonomously (Discord TOS compliance)

### Content Templates

**Progress Update:**
```
🏭 FactoryLM Cookoff Update — Day X

[What I built today]
[Screenshot or short video]
[What's next]
[Any questions for the community]

GitHub: github.com/Mikecranesync/factorylm
```

**Technical Share:**
```
🔧 Quick tip for Cosmos Reason 2 + industrial video:

[Insight or technique]
[Code snippet or config]
[Results / what worked / what didn't]
```

---

## Phase 5: Automation (Nice-to-Have)

Once the basic bot works, add scheduled posting:

- **Daily standup post** — auto-generated from git commits + COOKOFF_PLAN.md checklist status
- **Incident demo replay** — trigger a sim fault, capture Cosmos insight, post to Discord
- **Community monitor** — watch for keywords like "PLC", "industrial", "factory", "modbus" and alert Mike to relevant threads

---

## Environment Variables

```bash
DISCORD_BOT_TOKEN=          # From Discord Developer Portal
OPENCLAW_GATEWAY_URL=       # http://localhost:18800
NVIDIA_COSMOS_API_KEY=      # From build.nvidia.com (model-specific)
```

---

## Resources to Research

| Resource | URL | Purpose |
|----------|-----|---------|
| discord.py docs | https://discordpy.readthedocs.io | Python Discord bot library |
| Discord Developer Portal | https://discord.com/developers | Bot registration |
| NVIDIA Omniverse Discord | https://discord.com/invite/nvidiaomniverse | Cosmos Cookoff community |
| Cosmos Cookoff page | https://luma.com/nvidia-cosmos-cookoff | Official rules, dates |
| Cosmos Cookbook | https://nvidia-cosmos.github.io/cosmos-cookbook/ | Recipes for Reason 2 |
| Cosmos Reason 2 GitHub | https://github.com/nvidia-cosmos/cosmos-reason2 | Source code + docs |
| build.nvidia.com | https://build.nvidia.com/nvidia/cosmos-reason2-8b | API playground + key |
| Worker Safety recipe | cosmos-cookbook → recipes/inference/reason2/worker_safety | Most relevant recipe for industrial use |
| Clawdbot WhatsApp adapter | docs/adapters/WHATSAPP_SETUP.md | Pattern to follow for Discord |

---

## Timeline

| Day | Task | Time |
|-----|------|------|
| **Today (Feb 17)** | Get Cosmos API key from build.nvidia.com | 30 min |
| **Today** | Register Discord bot, get token | 30 min |
| **Today** | Build standalone `bot.py` (Option A) | 2 hrs |
| **Today** | First post in Cookoff Discord — intro + architecture | 30 min |
| **Feb 18-19** | Wire bot to OpenClaw gateway for autonomous replies | 3 hrs |
| **Feb 18-19** | Post progress update with Cosmos working demo | 1 hr |
| **Feb 20-24** | Daily community engagement (answer questions, share progress) | 30 min/day |
| **Feb 25** | Final demo teaser post | 30 min |
| **Feb 26** | Submission post + celebration | 30 min |

---

## Success Metrics

- [ ] Bot is live in NVIDIA Discord
- [ ] At least 5 progress posts shared
- [ ] At least 3 questions answered for other contestants
- [ ] At least 1 collaboration formed
- [ ] FactoryLM recognized by at least 1 NVIDIA staff member
- [ ] Demo video linked in Discord before submission

---

*This plan is about being PRESENT and HELPFUL in the community — not just showing up on submission day.*
