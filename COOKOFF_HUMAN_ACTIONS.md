# 🎯 Cosmos Cookoff — Human Actions Required

**Date:** Feb 17, 2026 | **Deadline:** Feb 26, 2026 (9 days)  
**What's already done programmatically:** Discord bot code built (`services/discord-adapter/bot.py`), discord.py installed, Cosmos client updated to read your Doppler key, Llama fallback verified working.

---

## ⚡ Action 1: Get Cosmos Reason 2 Model Access (15 min)

Your NVIDIA API key (`nvapi-tWnO5Q...`) works but returns **404 for cosmos-reason2-8b** — it's not enabled on your account.

### Steps:
1. Open **[build.nvidia.com/nvidia/cosmos-reason2-8b](https://build.nvidia.com/nvidia/cosmos-reason2-8b)**
2. Sign in with your NVIDIA account
3. Click **"Get API Key"** (top right, green button)
4. If it says "Generate Key" — generate a new one. This key will be scoped to Cosmos models
5. **Test it right there** — upload a short video in the playground, click Run
6. Copy the new key

### Then run this in PowerShell:
```powershell
doppler secrets set NVIDIA_COSMOS_API_KEY "nvapi-YOUR-NEW-KEY" --project factorylm --config dev
```

### Verify it works:
```powershell
doppler run --project factorylm --config dev -- python -c "from cosmos.client import CosmosClient; c = CosmosClient(); print('Available:', c.is_available()); i = c.analyze_incident('TEST', 'sim', {'error_code': 3, 'motor_current': 8.5}); print('Model:', i.cosmos_model, '| Summary:', i.summary[:80])"
```

If it still says `meta/llama-3.1-70b-instruct` as the model, the key isn't scoped to Cosmos. Ask in Discord (see Action 3).

---

## ⚡ Action 2: Register Discord Bot (10 min)

### Steps:
1. Open **[discord.com/developers/applications](https://discord.com/developers/applications)**
2. Click **"New Application"** → Name: **FactoryLM**
3. Go to **Bot** tab (left sidebar)
4. Click **"Reset Token"** → **Copy the token** (you only see it once!)
5. Under **Privileged Gateway Intents**, enable:
   - ✅ **MESSAGE CONTENT INTENT**
   - ✅ **SERVER MEMBERS INTENT**
6. Go to **OAuth2** → **URL Generator**
   - Scopes: check `bot`
   - Bot Permissions: check `Send Messages`, `Read Message History`, `Embed Links`, `Attach Files`, `Add Reactions`
7. **Copy the generated URL** at the bottom
8. **Open that URL in your browser** → Select the **NVIDIA Omniverse** server → Authorize

### Then run this in PowerShell:
```powershell
doppler secrets set DISCORD_BOT_TOKEN "YOUR-BOT-TOKEN" --project factorylm --config dev
```

### Start the bot:
```powershell
cd c:\Users\hharp\OneDrive\Desktop\FactoryLM
doppler run --project factorylm --config dev -- python services/discord-adapter/bot.py
```

You should see: `✅ FactoryLM is online as FactoryLM#1234`

---

## ⚡ Action 3: Post in Cosmos Cookoff Discord (5 min)

### Join/find the channels:
1. Make sure you're in the **NVIDIA Omniverse Discord** (invite: `discord.com/invite/nvidiaomniverse`)
2. Find the **#cosmos-cookoff** or **#questions** channel

### Post this intro (copy-paste):

```
🏭 Hey everyone — Mike from FactoryLM here.

Building an industrial AI platform for the Cookoff that connects to real PLCs (Allen-Bradley Micro 820) via Modbus TCP, streams tag data through a central pipeline, and uses Cosmos Reason 2 to diagnose equipment faults from video + sensor data.

The pipeline: PLC tags + factory floor video → incident bundle → Cosmos Reason 2 → structured root-cause analysis delivered to the operator's phone via Telegram.

Quick question: is cosmos-reason2-8b available via the NIM API (integrate.api.nvidia.com)? My API key works for other models but gets a 404 on cosmos-reason2-8b. Do I need a separate key from build.nvidia.com, or is self-hosting the only option?

GitHub: https://github.com/Mikecranesync/factorylm
Architecture: https://gist.github.com/Mikecranesync/e8f95da626fd0b4adcb8df13bb62ba96
```

### If someone answers the API question:
- If you need a **different key**: generate it and run the `doppler secrets set` command from Action 1
- If you need to **self-host**: you'll need a GPU server (check if Nebius sponsorship covers this — they're a Cookoff sponsor)

---

## ⚡ Action 4: Start Docker for Postgres (2 min)

```powershell
cd c:\Users\hharp\OneDrive\Desktop\FactoryLM\infra\local
docker-compose up -d
```

If `docker-compose.yml` doesn't exist yet, run this:
```powershell
# Minimal Postgres for the cookoff
docker run -d --name factorylm-postgres -e POSTGRES_PASSWORD=factorylm -e POSTGRES_DB=matrix_dev -p 5432:5432 postgres:16-alpine
```

---

## 📋 After All Actions — Verify Everything

Run this checklist in PowerShell:

```powershell
# 1. Cosmos API key works
doppler run --project factorylm --config dev -- python -c "from cosmos.client import CosmosClient; c = CosmosClient(); print('Cosmos available:', c.is_available())"

# 2. Discord bot token exists
doppler secrets get DISCORD_BOT_TOKEN --project factorylm --config dev --plain 2>$null | ForEach-Object { if ($_) { Write-Host 'Discord token: SET' } else { Write-Host 'Discord token: MISSING' } }

# 3. Discord bot starts
doppler run --project factorylm --config dev -- python -c "import discord; print('discord.py version:', discord.__version__)"

# 4. Postgres running
docker ps --filter name=postgres --format '{{.Names}} {{.Status}}' 2>$null || Write-Host 'Docker: not running'
```

---

## 🗓 What Happens After These Actions

| Day | What Gets Unlocked | Who Does It |
|-----|-------------------|-------------|
| **Today** | Cosmos Reason 2 real API calls (not just Llama fallback) | Actions 1 + 3 |
| **Today** | Bot live in NVIDIA Discord, responding to @mentions | Action 2 |
| **Today** | Postgres storing tag history for demos | Action 4 |
| **Feb 18-19** | End-to-end demo: Factory I/O fault → Cosmos insight → Discord post | Automated |
| **Feb 20-24** | Daily progress posts in Discord (bot or manual) | Mike |
| **Feb 25-26** | Demo video + submission | Mike |

---

*Total human time: ~30 minutes. Everything else is already built or will be automated.*
