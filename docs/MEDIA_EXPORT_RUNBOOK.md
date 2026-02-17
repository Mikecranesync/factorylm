# Media Export Runbook

## Quick Start - Free Up Storage NOW

### Option 1: Send to Gus Bot (Easiest)
Just send photos/videos to Gus in Telegram. They auto-sync to Google Drive.

```
Phone → Open Telegram → Send to Gus → Done
```

### Option 2: Run Export Script (Laptops)
```powershell
# Preview what would be exported
.\scripts\media-export-cleanup.ps1 -DryRun

# Export only (no delete)
.\scripts\media-export-cleanup.ps1

# Export AND delete files older than 30 days
.\scripts\media-export-cleanup.ps1 -Cleanup -DaysOld 30
```

---

## Complete Media Pipeline

### Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         MEDIA SOURCES                                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │
│  │ Travel      │  │ PLC         │  │ Phone       │  │ Telegram    │   │
│  │ Laptop      │  │ Laptop      │  │ Camera      │  │ to Gus      │   │
│  │             │  │             │  │             │  │             │   │
│  │ Screenshots │  │ Factory I/O │  │ Photos      │  │ Direct      │   │
│  │ Videos      │  │ Recordings  │  │ Videos      │  │ Upload      │   │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘   │
│         │                │                │                │           │
│         ▼                ▼                ▼                ▼           │
│  ┌──────────────────────────────────────────────────────────────────┐ │
│  │                    GOOGLE DRIVE (2TB)                            │ │
│  │                 gdrive:factorylm-archives/media/                 │ │
│  │                                                                  │ │
│  │  /travel-laptop/2026-02-17/                                     │ │
│  │  /plc-laptop/2026-02-17/                                        │ │
│  │  /phone/2026-02-17/                                             │ │
│  │  /telegram/2026-02-17/                                          │ │
│  └──────────────────────────────────────────────────────────────────┘ │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Device-Specific Instructions

### Travel Laptop (Windows)

**Automatic:** Run media offload agent as background service
```powershell
# Start media offload agent (polls every 60 seconds)
python services/media/media_offload_agent.py

# Or run once
python services/media/media_offload_agent.py --once
```

**Manual:** One-time export
```powershell
# From FactoryLM directory
.\scripts\media-export-cleanup.ps1 -DryRun
.\scripts\media-export-cleanup.ps1
```

**Watch Folders:**
- `Desktop\Captures\`
- `Downloads\Screenshots\`
- `Pictures\Screenshots\`
- `Videos\Captures\`

---

### PLC Laptop (Windows)

**Automatic:** Accessed remotely via Jarvis Node
```
Travel Laptop runs media offload agent
  → Connects to PLC laptop (100.72.2.99:8765)
  → Downloads new files
  → Syncs to Google Drive
```

**Manual:** Run export script on PLC laptop directly
```powershell
.\scripts\media-export-cleanup.ps1
```

**Watch Folders:**
- `Pictures\Screenshots\`
- `Videos\FactoryIO\`
- `Desktop\PLCExports\`

---

### iPhone

**Option A: Telegram (Recommended)**
1. Take photo/video
2. Open Telegram
3. Send to Gus bot
4. Done - auto-synced to Google Drive

**Option B: OneDrive Camera Upload**
1. Install OneDrive app
2. Enable "Camera Upload"
3. Photos sync to `OneDrive\Pictures\Camera Roll`
4. Export script picks them up

**Option C: iCloud to Windows**
1. Install iCloud for Windows
2. Enable Photos sync
3. Photos appear in `%USERPROFILE%\iCloudPhotos`
4. Export script picks them up

**Option D: Google Photos**
1. Install Google Photos app
2. Enable backup
3. Use Google Photos API to pull to Drive
4. (Requires OAuth setup)

---

### Android Phone

**Option A: Telegram (Recommended)**
Same as iPhone - send to Gus bot.

**Option B: USB Transfer**
1. Connect phone to laptop via USB
2. Phone appears as `D:\` or `E:\` drive
3. Export script checks `D:\Phone\DCIM` and `E:\Phone\DCIM`

**Option C: Google Photos**
Built-in backup - use API to sync.

---

## Cleanup Guidelines

### Safe to Delete (After Sync)
- Screenshots older than 30 days
- Video recordings older than 30 days
- Downloaded media (already has source)
- Telegram downloaded media

### Keep Forever
- Original camera photos (sync, don't delete)
- Important project files
- Configuration files

### Cleanup Schedule
```powershell
# Weekly cleanup (delete files older than 30 days that are synced)
.\scripts\media-export-cleanup.ps1 -Cleanup -DaysOld 30

# Monthly deep clean (delete files older than 7 days)
.\scripts\media-export-cleanup.ps1 -Cleanup -DaysOld 7
```

---

## Prerequisites

### rclone Setup
```powershell
# Install rclone
winget install Rclone.Rclone

# Configure Google Drive remote
rclone config
# Name: gdrive
# Type: drive (Google Drive)
# Follow OAuth prompts

# Verify setup
rclone lsd gdrive:
```

### Verify Connection
```powershell
# Check Google Drive remote
rclone ls gdrive:factorylm-archives/

# Check PLC laptop (Jarvis Node)
curl http://100.72.2.99:8765/health
```

---

## Storage Targets

| Location | Current | Target | Action |
|----------|---------|--------|--------|
| Travel Laptop | ? GB | < 50 GB media | Weekly cleanup |
| PLC Laptop | ? GB | < 20 GB media | Weekly cleanup |
| Phone | ? GB | < 5 GB photos | Send to Telegram |
| Google Drive | ? GB / 2 TB | Unlimited | Archive everything |

---

## Content Pipeline Integration

Once media is in Google Drive, it's available for:

1. **YouTube Shorts Production**
   - Images → Ken Burns video assembly
   - Audio → Voice narration
   - Output → 9:16 vertical shorts

2. **Knowledge Base**
   - Equipment photos → OCR → CMMS
   - Documentation → Vector DB

3. **Training Data**
   - Telegram logs → Conversation pairs
   - Screenshots → Visual examples

---

## Troubleshooting

### rclone: "remote not found"
```powershell
rclone config
# Re-create gdrive remote
```

### Jarvis Node offline
```powershell
# Check PLC laptop is online
ping 100.72.2.99

# Check Jarvis Node is running
curl http://100.72.2.99:8765/health
```

### Files not syncing
```powershell
# Check staging directory
ls $env:USERPROFILE\.openclaw\media-staging\

# Check logs
cat $env:USERPROFILE\.openclaw\logs\media-export-*.log
```

### Permission denied
```powershell
# Run as administrator
Start-Process powershell -Verb RunAs
```

---

## Quick Reference

| Task | Command |
|------|---------|
| Preview export | `.\scripts\media-export-cleanup.ps1 -DryRun` |
| Export only | `.\scripts\media-export-cleanup.ps1` |
| Export + cleanup | `.\scripts\media-export-cleanup.ps1 -Cleanup` |
| Start agent | `python services/media/media_offload_agent.py` |
| Single run | `python services/media/media_offload_agent.py --once` |
| Check Drive | `rclone ls gdrive:factorylm-archives/media/` |
