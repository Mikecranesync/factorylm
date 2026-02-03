# WhatsApp Adapter Setup Guide

Quick setup guide for WhatsApp integration with Clawdbot/FactoryLM.

## Overview

WhatsApp integration uses Clawdbot's gateway with Baileys (WhatsApp Web protocol). This enables:
- Direct messaging with field technicians
- Photo intake for equipment diagnostics
- Voice note support
- Group chat integration

## Prerequisites

- Clawdbot gateway running (see Infrastructure section)
- Dedicated phone number (recommended) OR personal number
- Node.js 22+

## Quick Start (5 Minutes)

### Step 1: Get a Phone Number

**Fastest options (eSIM - instant activation):**

| Provider | Cost | Notes |
|----------|------|-------|
| Mint Mobile | $15/3mo | US number, eSIM, reliable |
| Google Fi | $20/mo | eSIM, real number |
| T-Mobile Prepaid | $10 | US, instant eSIM |
| giffgaff (UK) | Free | No contract |

**Key insight:** The number only needs to receive ONE SMS for verification. After that, WhatsApp Web sessions persist via `creds.json`.

**Avoid:** TextNow, Google Voice, most virtual numbers - WhatsApp blocks these.

### Step 2: Register WhatsApp

On a phone with the new number:
1. Install WhatsApp (or WhatsApp Business for separate app)
2. Register with the new number
3. Complete verification via SMS

### Step 3: Link to Clawdbot

On the server running Clawdbot:

```bash
# Start the login flow (shows QR code)
clawdbot channels login
```

On your phone:
1. WhatsApp → Settings → Linked Devices
2. Tap "Link a Device"
3. Scan the QR code from the terminal

### Step 4: Configure for Open Access

Edit `~/.clawdbot/clawdbot.json`:

```json
{
  "channels": {
    "whatsapp": {
      "dmPolicy": "open",
      "allowFrom": ["*"],
      "groupPolicy": "open",
      "groups": ["*"],
      "sendReadReceipts": true,
      "ackReaction": {
        "emoji": "👀",
        "direct": true,
        "group": "always"
      }
    }
  }
}
```

### Step 5: Restart Gateway

```bash
pkill -9 -f clawdbot-gateway || true
nohup clawdbot gateway run --bind loopback --port 18789 --force > /tmp/clawdbot-gateway.log 2>&1 &
```

### Step 6: Verify

```bash
clawdbot channels status --probe
```

## Configuration Options

### DM Policies

| Policy | Description |
|--------|-------------|
| `open` | Anyone can message (requires `allowFrom: ["*"]`) |
| `allowlist` | Only numbers in `allowFrom` can message |
| `pairing` | Unknown senders get a pairing code to approve |
| `disabled` | DMs disabled |

### Allowlist Examples

```json
{
  "channels": {
    "whatsapp": {
      "dmPolicy": "allowlist",
      "allowFrom": [
        "+15551234567",
        "+15559876543"
      ]
    }
  }
}
```

### Group Settings

```json
{
  "channels": {
    "whatsapp": {
      "groupPolicy": "open",
      "groups": ["*"],
      "historyLimit": 50
    }
  }
}
```

### Auto-Reactions

Acknowledge messages immediately with an emoji:

```json
{
  "channels": {
    "whatsapp": {
      "ackReaction": {
        "emoji": "👀",
        "direct": true,
        "group": "always"
      }
    }
  }
}
```

## Multi-Account Setup

Run multiple WhatsApp accounts on one gateway:

```bash
# Link additional account
clawdbot channels login --account work
clawdbot channels login --account personal
```

Configure per-account:

```json
{
  "channels": {
    "whatsapp": {
      "accounts": {
        "work": {
          "dmPolicy": "allowlist",
          "allowFrom": ["+15551234567"]
        },
        "personal": {
          "dmPolicy": "open",
          "allowFrom": ["*"]
        }
      }
    }
  }
}
```

## Infrastructure

### DigitalOcean Deployment

Server IP: `165.245.138.91` (update as needed)

Services running:
- Clawdbot Gateway: port 18789
- Flowise: port 3001
- n8n: port 5678
- CMMS: port 8080

### Restart Commands

```bash
# SSH to server
ssh root@165.245.138.91

# Restart gateway
pkill -9 -f clawdbot-gateway || true
nohup clawdbot gateway run --bind loopback --port 18789 --force > /tmp/clawdbot-gateway.log 2>&1 &

# Check logs
tail -f /tmp/clawdbot-gateway.log

# Verify status
clawdbot channels status --probe
ss -ltnp | grep 18789
```

### Troubleshooting

**Not linked / QR login required:**
```bash
clawdbot channels login
```

**Linked but disconnected:**
```bash
clawdbot doctor
# or restart gateway
```

**Check logs:**
```bash
tail -n 100 /tmp/clawdbot-gateway.log
```

## Testing

```bash
# Send a test message
clawdbot message send --to +1234567890 --message "Hello from FactoryLM"

# Send with media
clawdbot message send --to +1234567890 --message "Equipment photo" --media /path/to/image.jpg

# Interactive agent
clawdbot agent --message "Test prompt" --thinking low
```

## Integration with FactoryLM

WhatsApp can trigger FactoryLM workflows:

1. **Photo → CMMS Work Order** (via plc-copilot)
   - Technician sends equipment photo
   - Gemini Vision analyzes
   - Work order created automatically

2. **Diagnostic Queries**
   - "Siemens V20 F0001 fault"
   - Returns fix instructions with manual page numbers

3. **Equipment Status**
   - Query PLC status via natural language
   - Receive real-time I/O state

## Security Considerations

- Use dedicated number (not personal) for production
- Set `dmPolicy: "allowlist"` for restricted access
- Credentials stored in `~/.clawdbot/credentials/whatsapp/`
- Back up `creds.json` - losing it requires re-linking

## Related Documentation

- [Clawdbot Docs](https://docs.clawd.bot)
- [WhatsApp Channel Docs](https://docs.clawd.bot/channels/whatsapp)
- [services/ADAPTER_COMPARISON.md](../services/ADAPTER_COMPARISON.md)

---

**Created:** 2026-01-30
**Status:** Ready for dedicated phone number setup
**Next Steps:** Acquire eSIM, complete linking, test with field technicians
