# JARVIS Fix - Resume Prompt

**Date**: 2026-02-14
**Issue**: @UltronVPS_bot (Clawdbot) was "lobotomized" - giving dumb canned responses like "Gus on the floor" and "Come again?"

---

## Problem Summary

The Telegram bot @UltronVPS_bot had several issues:
1. **Limited persona**: Stuck in narrow "factory diagnosis only" mode
2. **Canned responses**: "Gus on the floor", "Come again?" instead of intelligent conversation
3. **No control capabilities**: Couldn't inject faults or control Factory I/O
4. **Config was restrictive**: Feb 8 changes set `dmPolicy: "allowlist"` (restored to `"open"`)

---

## What Was Fixed

### 1. Restored Clawdbot Config
- **File**: `/root/.clawdbot/clawdbot.json` on VPS (100.68.120.99)
- **Changes**:
  - `dmPolicy: "open"` (was "allowlist")
  - `allowFrom: ["*"]` (was restricted to single user)
  - Restored from Jan 31 backup

### 2. Created New JARVIS System Prompt
- **File**: `/root/jarvis-workspace/CLAUDE.md` on VPS
- **Content**: Full AI assistant persona with:
  - General intelligence (answer ANY question)
  - Factory diagnostics as specialty (not only capability)
  - Multi-node control instructions (PLC, Travel, VPS)
  - Factory I/O automation commands

### 3. Created Factory I/O Automator
- **File**: `C:/Users/hharp/OneDrive/Desktop/FactoryLM/scripts/factoryio_automator.py` on PLC laptop
- **Capabilities**:
  - `screenshot` - Take screenshot of Factory I/O
  - `click <x> <y>` - Click at coordinates
  - `push_box` - Push box off conveyor (fault injection)
  - `inject_fault <type>` - Inject specific fault (sensor_fail, motor_stop, box_jam, emergency)
  - `get_mouse_pos` - Get current mouse position
  - `move_to <x> <y>` - Move mouse
  - `press <key>` - Press keyboard key

---

## Key Files

| Location | File | Purpose |
|----------|------|---------|
| VPS | `/root/.clawdbot/clawdbot.json` | Clawdbot config |
| VPS | `/root/jarvis-workspace/CLAUDE.md` | JARVIS system prompt |
| PLC Laptop | `scripts/factoryio_automator.py` | Factory I/O control |
| This Repo | `services/telegram/friday_bot.py` | FRIDAY bot with AI |
| This Repo | `services/telegram/telegram_router.py` | Multi-node routing |

---

## How to Test

1. **Message @UltronVPS_bot on Telegram**
2. **Send**: "Who are you?" → Should respond as JARVIS, not "Gus"
3. **Send**: "Push a box off the conveyor" → Should execute automator
4. **Send**: `/reset` if still getting canned responses (clears session)

---

## How to Resume Work

### If bot is still dumb:
```bash
# SSH to VPS
ssh root@100.68.120.99

# Check service status
systemctl status clawdbot

# View logs
journalctl -u clawdbot -f

# Restart service
systemctl restart clawdbot

# Verify CLAUDE.md is in place
cat /root/jarvis-workspace/CLAUDE.md
```

### If Factory I/O control doesn't work:
```bash
# Test automator directly on PLC laptop
curl -X POST http://100.72.2.99:8765/shell \
  -H "Content-Type: application/json" \
  -d '{"command": "python C:/Users/hharp/OneDrive/Desktop/FactoryLM/scripts/factoryio_automator.py get_mouse_pos"}'
```

### To update JARVIS personality:
Edit `/root/jarvis-workspace/CLAUDE.md` on VPS, then restart clawdbot.

---

## Network Topology

```
Phone (Telegram)
      │
      ▼
VPS (100.68.120.99)
├── Clawdbot (@UltronVPS_bot)
├── CLAUDE.md (JARVIS persona)
└── Routes to:
    ├── PLC Laptop (100.72.2.99:8765)
    │   ├── Jarvis Node API
    │   ├── Factory I/O
    │   ├── Micro 820 PLC
    │   └── factoryio_automator.py
    │
    └── Travel Laptop (100.83.251.23:8765)
        └── Jarvis Node API
```

---

## Commands Reference

### Factory I/O Automator (run on PLC laptop via Jarvis Node)
```bash
python factoryio_automator.py screenshot
python factoryio_automator.py click 500 400
python factoryio_automator.py push_box
python factoryio_automator.py inject_fault box_jam
python factoryio_automator.py get_mouse_pos
python factoryio_automator.py move_to 800 600
python factoryio_automator.py press space
```

### Clawdbot CLI (on VPS)
```bash
clawdbot gateway status
clawdbot message send --target '8445149012' --channel telegram --message 'Test'
clawdbot plugins list
clawdbot skills list
clawdbot agents list
```

---

## Related Commits
- dc89cc4: FRIDAY bot with AI intelligence and media handlers
- Previous: Clawdbot config restoration from Jan 31 backup
