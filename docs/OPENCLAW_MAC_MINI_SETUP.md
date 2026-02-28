# OpenClaw Mac Mini Setup — First Boot to Always-On AI Home Base

**Machine:** Mac Mini "Macaroni"
**Instance ID:** `oc_macaroni`
**Bot:** `@Tony_Macaroni_bot`
**Role:** 5th device in the Tailscale mesh — dedicated always-on OpenClaw home base

---

## Part 1 — First Boot (macOS Basics for a Windows User)

### Power On & Initial Setup

1. Plug in power, monitor (HDMI/USB-C), keyboard, mouse
2. Press the power button (bottom of the back panel)
3. Walk through the setup wizard:
   - **Language:** English
   - **Region:** United States
   - **Wi-Fi:** Connect to your home network
   - **Apple ID:** Skip for now (click "Set Up Later" → "Skip")
   - **Account name:** `Macaroni` (this creates `/Users/Macaroni`)
   - **Password:** Set something you'll remember

### Quick Orientation — Windows → macOS Rosetta Stone

| Windows | macOS | Notes |
|---------|-------|-------|
| File Explorer | **Finder** | Click the smiley face in the dock |
| CMD / PowerShell | **Terminal** | Search "Terminal" in Spotlight |
| Start Menu search | **Spotlight** (`Cmd + Space`) | This is your best friend |
| `C:\Users\you` | `/Users/Macaroni` (aka `~`) | No drive letters on Mac |
| Task Manager | **Activity Monitor** | Search in Spotlight |
| Control Panel | **System Settings** | Apple menu (top-left) → System Settings |
| `Ctrl` key | **`Cmd` key** | Copy = `Cmd+C`, Paste = `Cmd+V` |
| Right-click | **Two-finger click** on trackpad, or `Ctrl+Click` |
| `.exe` installer | **`.dmg`** or **`brew install`** | Homebrew is the package manager |

### Key Differences from Windows

- **No `C:\`** — paths use forward slashes: `/Users/Macaroni/Documents`
- **Home directory** is `~` which means `/Users/Macaroni`
- **Hidden files** start with `.` (like `.openclaw/`). Show them in Finder: `Cmd + Shift + .`
- **Installing apps**: drag `.dmg` contents to Applications, or use `brew install` from Terminal
- **Closing windows** (red X) doesn't quit the app — use `Cmd + Q` to fully quit

### System Settings to Change Now

Open **System Settings** (Apple menu → System Settings):

1. **General → Sharing → Remote Login** → Toggle ON (this enables SSH so you can connect from other machines)
2. **Set hostname:**
   ```bash
   # Open Terminal (Cmd+Space → type "Terminal" → Enter)
   sudo scutil --set HostName macaroni
   sudo scutil --set LocalHostName macaroni
   sudo scutil --set ComputerName macaroni
   ```
3. **Lock Screen** → Set "Turn display off" to a short time but keep the machine awake (we'll handle sleep prevention in Part 9)

---

## Part 2 — Developer Tools

Open **Terminal** (Spotlight → "Terminal"):

```bash
# Step 1: Xcode command line tools (required before anything else)
# This installs git, clang, make, etc. — say Yes to the popup
xcode-select --install
# Wait for the install to finish (may take a few minutes)

# Step 2: Homebrew (macOS package manager — like winget/choco for Windows)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# IMPORTANT: After Homebrew installs, it tells you to run two commands.
# They look like this (copy the EXACT lines it gives you):
echo >> /Users/Macaroni/.zprofile
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> /Users/Macaroni/.zprofile
eval "$(/opt/homebrew/bin/brew shellenv)"

# Step 3: Core tools
brew install node@22 python@3.12 git gh jq

# Step 4: Link node@22 (brew won't add it to PATH by default)
brew link node@22

# Verify everything works
node --version    # Should show v22.x
python3 --version # Should show 3.12.x
git --version
gh --version
```

### Authenticate GitHub CLI

```bash
gh auth login
# Choose: GitHub.com → HTTPS → Yes (authenticate with browser) → Login with browser
# This opens Safari — log in with Mike's GitHub account
```

---

## Part 3 — Tailscale (Join the Mesh)

Tailscale creates a private network between all your devices. After this step, Macaroni can talk to the VPS, PLC laptop, and travel laptop.

```bash
# Install Tailscale
brew install tailscale

# Start the Tailscale service
brew services start tailscale

# Join the mesh
tailscale up --hostname=macaroni

# This opens a browser to authenticate — log in with your Tailscale account
```

After authenticating:

```bash
# Get Macaroni's Tailscale IP (record this — you'll need it)
tailscale ip -4
# Should show something like 100.x.x.x

# Test connectivity to other devices
ping -c 3 100.68.120.99   # VPS (Ultron)
ping -c 3 100.72.2.99     # PLC laptop
ping -c 3 100.83.251.23   # Travel laptop
```

> **Write down the `100.x.x.x` IP** — you'll need it for the instance map.

---

## Part 4 — OpenClaw Installation

```bash
# Install clawdbot (the OpenClaw runtime)
npm install -g clawdbot

# Install Claude Code CLI
npm install -g @anthropic-ai/claude-code

# Verify
openclaw --version
claude --version

# Clone the workspace
cd ~
git clone https://github.com/mikecranesync/openclaw-workspace.git ~/openclaw-workspace
cd ~/openclaw-workspace
cp .env.example .env
```

Edit the `.env` file:

```bash
nano ~/openclaw-workspace/.env
# Fill in:
#   ANTHROPIC_API_KEY=<from MACARONI.txt>
#   TELEGRAM_BOT_TOKEN=8760221174:AAFADxGkL71U_X8NoWLrY6htsg7awOFfxHE
#   TELEGRAM_USER_ID=8445149012
```

> **Nano crash course:** Arrow keys to move, type to edit, `Ctrl+O` then `Enter` to save, `Ctrl+X` to exit.

---

## Part 5 — Configuration (`~/.openclaw/openclaw.json`)

```bash
# Create the config directory
mkdir -p ~/.openclaw
```

Create the config file:

```bash
nano ~/.openclaw/openclaw.json
```

Paste the following (edit the `ANTHROPIC_API_KEY` placeholder with the real key from MACARONI.txt):

```json
{
  "meta": {
    "lastTouchedVersion": "2026.2.23",
    "lastTouchedAt": "2026-02-23T00:00:00.000Z"
  },
  "env": {
    "GROQ_API_KEY": "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",
    "DEEPSEEK_API_KEY": "sk-4a1441bac66940a3adc83e31e33987c0",
    "CEREBRAS_API_KEY": "csk-2dfv34kpm68fnx6r4twhdk8n8jye5wjhmtjtd2v9nncwd3mh",
    "OPENROUTER_API_KEY": "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"
  },
  "models": {
    "providers": {
      "groq": {
        "baseUrl": "https://api.groq.com/openai/v1",
        "apiKey": "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",
        "api": "openai-completions",
        "models": [
          {
            "id": "moonshotai/kimi-k2-instruct",
            "name": "Kimi K2 (Groq)",
            "reasoning": false,
            "input": ["text"],
            "cost": { "input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0 },
            "contextWindow": 131072,
            "maxTokens": 16384
          },
          {
            "id": "meta-llama/llama-4-maverick-17b-128e-instruct",
            "name": "Llama 4 Maverick (Groq)",
            "reasoning": false,
            "input": ["text"],
            "cost": { "input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0 },
            "contextWindow": 131072,
            "maxTokens": 32768
          },
          {
            "id": "qwen/qwen3-32b",
            "name": "Qwen3 32B (Groq)",
            "reasoning": true,
            "input": ["text"],
            "cost": { "input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0 },
            "contextWindow": 131072,
            "maxTokens": 32768
          },
          {
            "id": "llama-3.3-70b-versatile",
            "name": "Llama 3.3 70B (Groq)",
            "reasoning": false,
            "input": ["text"],
            "cost": { "input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0 },
            "contextWindow": 131072,
            "maxTokens": 32768
          }
        ]
      },
      "deepseek": {
        "baseUrl": "https://api.deepseek.com/v1",
        "apiKey": "sk-4a1441bac66940a3adc83e31e33987c0",
        "api": "openai-completions",
        "models": [
          {
            "id": "deepseek-reasoner",
            "name": "DeepSeek R1 Reasoner (671B)",
            "reasoning": true,
            "input": ["text"],
            "cost": { "input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0 },
            "contextWindow": 65536,
            "maxTokens": 8192
          },
          {
            "id": "deepseek-chat",
            "name": "DeepSeek V3 Chat",
            "reasoning": false,
            "input": ["text"],
            "cost": { "input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0 },
            "contextWindow": 65536,
            "maxTokens": 8192
          }
        ]
      },
      "cerebras": {
        "baseUrl": "https://api.cerebras.ai/v1",
        "apiKey": "csk-2dfv34kpm68fnx6r4twhdk8n8jye5wjhmtjtd2v9nncwd3mh",
        "api": "openai-completions",
        "models": [
          {
            "id": "gpt-oss-120b",
            "name": "GPT-OSS 120B (Cerebras)",
            "reasoning": false,
            "input": ["text"],
            "cost": { "input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0 },
            "contextWindow": 131072,
            "maxTokens": 8192
          }
        ]
      },
      "openrouter": {
        "baseUrl": "https://openrouter.ai/api/v1",
        "apiKey": "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",
        "api": "openai-completions",
        "models": [
          {
            "id": "nousresearch/hermes-3-llama-3.1-405b:free",
            "name": "Hermes 3 405B (OpenRouter Free)",
            "reasoning": false,
            "input": ["text"],
            "cost": { "input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0 },
            "contextWindow": 131072,
            "maxTokens": 16384
          },
          {
            "id": "meta-llama/llama-3.3-70b-instruct:free",
            "name": "Llama 3.3 70B (OpenRouter Free)",
            "reasoning": false,
            "input": ["text"],
            "cost": { "input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0 },
            "contextWindow": 131072,
            "maxTokens": 32768
          }
        ]
      }
    }
  },
  "agents": {
    "defaults": {
      "model": {
        "primary": "anthropic/claude-sonnet-4-20250514",
        "fallbacks": [
          "groq/moonshotai/kimi-k2-instruct",
          "groq/qwen/qwen3-32b",
          "deepseek/deepseek-chat",
          "groq/llama-3.3-70b-versatile",
          "openrouter/nousresearch/hermes-3-llama-3.1-405b:free"
        ]
      },
      "imageModel": {
        "primary": "google/gemini-2.5-flash",
        "fallbacks": [
          "anthropic/claude-sonnet-4-20250514"
        ]
      },
      "workspace": "/Users/Macaroni/openclaw-workspace",
      "compaction": {
        "mode": "safeguard",
        "reserveTokensFloor": 4000
      },
      "heartbeat": {
        "every": "2h",
        "target": "telegram",
        "to": "8445149012"
      },
      "maxConcurrent": 4,
      "subagents": {
        "maxConcurrent": 3,
        "model": {
          "primary": "groq/moonshotai/kimi-k2-instruct",
          "fallbacks": [
            "deepseek/deepseek-chat",
            "groq/llama-3.3-70b-versatile",
            "openrouter/meta-llama/llama-3.3-70b-instruct:free"
          ]
        }
      }
    }
  },
  "tools": {},
  "messages": {
    "ackReaction": "\ud83d\udc40",
    "ackReactionScope": "all",
    "removeAckAfterReply": false
  },
  "commands": {
    "native": "auto",
    "nativeSkills": "auto"
  },
  "channels": {
    "telegram": {
      "enabled": true,
      "dmPolicy": "allowlist",
      "botToken": "8760221174:AAFADxGkL71U_X8NoWLrY6htsg7awOFfxHE",
      "allowFrom": [
        "8445149012"
      ],
      "groupPolicy": "disabled",
      "streamMode": "partial"
    }
  },
  "gateway": {
    "port": 18789,
    "mode": "local",
    "bind": "0.0.0.0",
    "auth": {
      "mode": "token",
      "token": "GENERATE_A_TOKEN_HERE"
    }
  },
  "plugins": {
    "entries": {
      "telegram": {
        "enabled": true
      },
      "diagnostics-otel": {
        "enabled": false
      }
    }
  }
}
```

> **Important:** Replace `GENERATE_A_TOKEN_HERE` with a random token. Generate one:
> ```bash
> node -e "console.log(require('crypto').randomBytes(24).toString('hex'))"
> ```

> **Note:** The `ANTHROPIC_API_KEY` is set via the workspace `.env`, not in this JSON. The gateway reads secrets from the JSON `env` block for providers like Groq, but the Anthropic key is picked up from the workspace environment.

---

## Part 6 — Telegram Bot (Already Created)

The bot `@Tony_Macaroni_bot` is already created via BotFather. No additional setup needed.

- **Bot username:** `@Tony_Macaroni_bot`
- **Token:** Already in `openclaw.json` → `channels.telegram.botToken`
- **Allowed user:** Mike's Telegram ID `8445149012`

To test: open Telegram on your phone, search for `@Tony_Macaroni_bot`, and send it a message after the gateway is running.

---

## Part 7 — Test Run

```bash
# Start the gateway
cd ~/openclaw-workspace
openclaw gateway --port 18789
```

You should see startup logs. Now test:

1. **From phone:** Open Telegram → message `@Tony_Macaroni_bot` → you should get a response
2. **From another Tailscale device** (e.g., travel laptop):
   ```bash
   curl http://<macaroni-tailscale-ip>:18789/health
   ```
   Should return a JSON health response.

If the bot responds: you're live. `Ctrl+C` to stop the gateway.

---

## Part 8 — Auto-Start on Boot (launchd)

macOS uses `launchd` instead of Windows Services or Linux systemd. This ensures OpenClaw starts automatically when the Mac boots.

First, find where `openclaw` is installed:

```bash
which openclaw
# Likely: /opt/homebrew/bin/openclaw
```

Create the log directory:

```bash
mkdir -p /tmp/openclaw
```

Create the launch agent:

```bash
nano ~/Library/LaunchAgents/ai.openclaw.gateway.plist
```

Paste (adjust the `openclaw` path if `which openclaw` gave a different result):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>ai.openclaw.gateway</string>
    <key>ProgramArguments</key>
    <array>
        <string>/opt/homebrew/bin/openclaw</string>
        <string>gateway</string>
        <string>--port</string>
        <string>18789</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>WorkingDirectory</key>
    <string>/Users/Macaroni/openclaw-workspace</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>HOME</key>
        <string>/Users/Macaroni</string>
        <key>NODE_ENV</key>
        <string>production</string>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    </dict>
    <key>StandardOutPath</key>
    <string>/tmp/openclaw/openclaw-stdout.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/openclaw/openclaw-stderr.log</string>
</dict>
</plist>
```

Load and verify:

```bash
# Load the service (starts immediately)
launchctl load ~/Library/LaunchAgents/ai.openclaw.gateway.plist

# Verify it's running
launchctl list | grep openclaw
# Should show a PID and "ai.openclaw.gateway"

# Check logs
tail -f /tmp/openclaw/openclaw-stdout.log
```

### Managing the service

```bash
# Stop
launchctl unload ~/Library/LaunchAgents/ai.openclaw.gateway.plist

# Start
launchctl load ~/Library/LaunchAgents/ai.openclaw.gateway.plist

# Restart (unload + load)
launchctl unload ~/Library/LaunchAgents/ai.openclaw.gateway.plist && \
launchctl load ~/Library/LaunchAgents/ai.openclaw.gateway.plist
```

---

## Part 9 — Prevent Sleep (Always-On)

This is critical — without this, the Mac will sleep and the bot goes offline.

```bash
# Prevent sleep entirely (even when display is off)
sudo pmset -a disablesleep 1
sudo pmset -a sleep 0
sudo pmset -a displaysleep 10    # Display can sleep after 10 min (saves energy)
sudo pmset -a disksleep 0        # Prevent disk sleep

# Verify settings
pmset -g
```

**Or via GUI:** System Settings → Energy → Toggle "Prevent automatic sleeping when the display is off" to ON.

---

## Part 10 — Mike's Brain (Knowledge Graph)

Mike's Brain is a vector-enabled knowledge graph that runs alongside OpenClaw. It uses Neon (serverless Postgres + pgvector) with worker processes (Herodotus = archivist, Hammurabi = QA judge).

Currently at v0.1.0 — schema exists, workers are skeletons. Getting it cloned and configured on Macaroni positions it to receive data from OpenClaw sessions once the ingestion pipeline is built.

```bash
# Clone
cd ~
git clone https://github.com/mikecranesync/mikes-brain.git ~/mikes-brain
cd ~/mikes-brain
cp .env.example .env

# Edit .env — fill in:
#   NEON_DATABASE_URL=<your Neon connection string>
#   OPENAI_API_KEY=<key>
#   ANTHROPIC_API_KEY=<from MACARONI.txt>
#   GITHUB_TOKEN=<your GitHub PAT>
#   TELEGRAM_SESSION_PATH=<path to clawdbot's session directory>
nano ~/mikes-brain/.env

# Create a virtual environment (keeps dependencies isolated)
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Initialize the Neon database schema
python scripts/init_db.py

# Test Herodotus (archivist worker)
python workers/herodotus.py

# Deactivate venv when done testing
deactivate
```

---

## Part 11 — Observability (Optional — Do Later)

These are nice-to-have. Get the bot responding first, then add observability.

### Axiom (Log Aggregation)

```bash
brew install vectordotdev/brew/vector

# Configure Vector to ship OpenClaw logs to Axiom
mkdir -p /etc/vector
# Config file goes at /etc/vector/vector.yaml — see ultron's config for reference
```

### Honeycomb (Distributed Tracing)

```bash
npm install -g @opentelemetry/sdk-node @opentelemetry/exporter-trace-otlp-http

# Create a tracing.js bootstrap file
# Set NODE_OPTIONS=-r /path/to/tracing.js in the launchd plist
# See scripts/honeycomb/ in the FactoryLM repo for examples
```

Both are fully optional for first boot.

---

## Quick Reference — All the Key Paths

| What | Path |
|------|------|
| Home directory | `/Users/Macaroni` |
| OpenClaw config | `~/.openclaw/openclaw.json` |
| Workspace | `~/openclaw-workspace/` |
| Workspace `.env` | `~/openclaw-workspace/.env` |
| LaunchAgent plist | `~/Library/LaunchAgents/ai.openclaw.gateway.plist` |
| Stdout log | `/tmp/openclaw/openclaw-stdout.log` |
| Stderr log | `/tmp/openclaw/openclaw-stderr.log` |
| Mike's Brain | `~/mikes-brain/` |
| Homebrew | `/opt/homebrew/` |
| Node/npm binaries | `/opt/homebrew/bin/` |

## Network — Tailscale Mesh After Setup

```
+-----------------------------------------------------------------+
|                        TAILSCALE MESH                           |
+-----------------------------------------------------------------+
|                                                                 |
|  Mac Mini (Macaroni)     VPS (Ultron)         PLC Laptop       |
|  100.x.x.x              100.68.120.99        100.72.2.99      |
|  +--------------+        +--------------+     +--------------+ |
|  | OpenClaw     |        | OpenClaw     |     | Jarvis Node  | |
|  | Gateway      |<------>| Gateway      |<--->| Factory I/O  | |
|  | Port 18789   |        | Port 18789   |     | Port 8765    | |
|  | @Tony_       |        | @UltronVPS_  |     | Micro 820    | |
|  |  Macaroni_bot|        |  bot         |     +--------------+ |
|  +--------------+        +--------------+                       |
|         ^                                     Travel Laptop    |
|         | Telegram                            100.83.251.23    |
|    +----+----+                                +--------------+ |
|    |  MIKE   |                                | Jarvis Node  | |
|    | (Phone) |                                | Port 8765    | |
|    +---------+                                +--------------+ |
|                                                                 |
+-----------------------------------------------------------------+
```

---

## Part 12 — Discovery Prompt (Give This to Claude Code)

Once Claude Code is running on the Mac and the setup is complete, paste this prompt to have the agent verify everything and report back:

> You are the new OpenClaw instance on Mac Mini "Macaroni". Read `docs/OPENCLAW_MAC_MINI_SETUP.md` in this repo for your setup guide. After setup, do a full discovery:
>
> 1. Report this machine's hardware (CPU, RAM, disk)
> 2. Report the Tailscale IP and ping all mesh devices (100.68.120.99 VPS, 100.72.2.99 PLC laptop, 100.83.251.23 travel laptop)
> 3. Hit every known health endpoint and report what's live:
>    - `curl http://100.68.120.99:18789/health` (VPS OpenClaw)
>    - `curl http://100.72.2.99:8765/health` (PLC laptop Jarvis Node)
>    - `curl http://100.83.251.23:8765/health` (Travel laptop Jarvis Node)
> 4. Verify the OpenClaw gateway starts and responds on this machine
> 5. Check clawdbot version matches across instances
> 6. Verify Telegram bot token is valid and can receive messages
> 7. Map the factorylm monorepo structure — read the README (the vision), read `docs/OPENCLAW_INSTANCES.md`
> 8. Send a test message summary to Telegram with the full status report

---

*All instances run the same codebase: https://github.com/Mikecranesync/clawdbot (private)*
*Instance map: `docs/OPENCLAW_INSTANCES.md` in the FactoryLM monorepo*
