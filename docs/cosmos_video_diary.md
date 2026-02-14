# Cosmos Video Diary

**Last Updated:** 2026-02-13  
**Status:** Architecture complete, stub analysis

---

## What It Is

The Cosmos Video Diary is a 24/7 footage watcher and auto-documentation system. It continuously:

1. **Watches** camera feeds or screen recordings
2. **Analyzes** each clip using NVIDIA Cosmos Reason 2 (currently stubbed)
3. **Identifies highlights** — faults, repairs, unusual activity
4. **Generates demo clips** — concatenated highlight reels for the Cookoff submission

This enables **asynchronous troubleshooting**: a technician can review what happened overnight without watching hours of footage. Cosmos captions each clip and flags the interesting moments.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                 24/7 RECORDING                           │
│  OBS Studio / ffmpeg / IP Camera                         │
│  Output: recordings/raw/ (5-min segments)                │
└───────────────────┬─────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────┐
│  VIDEO INGESTER (video/ingester.py)                      │
│  • Watches recordings/raw/ for new files                 │
│  • Chunks into 15-second clips with ffmpeg               │
│  • Stores clips in recordings/chunks/                    │
│  • Registers metadata in Matrix DB                       │
└───────────────────┬─────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────┐
│  COSMOS ANALYZER (video/cosmos_analyzer.py)               │
│  • Polls Matrix API for pending clips                    │
│  • Sends clip + context to Cosmos Reason 2               │
│  • Gets back: caption, key events, interesting score     │
│  • Marks highlights (score ≥ 60)                         │
│  • Links clips to PLC incidents by timestamp overlap     │
└───────────────────┬─────────────────────────────────────┘
                    │
              ┌─────┴──────┐
              ▼            ▼
┌──────────────────┐ ┌──────────────────────────────────┐
│  HIGHLIGHT       │ │  WEB HMI (http://localhost:8000)  │
│  SELECTOR        │ │  /video — Video Log page           │
│  + SHORT BUILDER │ │  Browse clips, view captions,      │
│  → Demo videos   │ │  filter by status/score            │
└──────────────────┘ └──────────────────────────────────┘
```

---

## Why This Matters for the Cookoff

The NVIDIA Cosmos Cookoff judges want to see **physical AI** applied to real problems. The Video Diary shows:

1. **Continuous monitoring** — not just one-off analysis, but 24/7 coverage
2. **Automatic documentation** — every fault is captioned and timestamped
3. **Asynchronous troubleshooting** — review overnight events in minutes
4. **Auto-generated demo clips** — the system builds its own highlight reel

---

## Quick Start

```bash
# 1. Start Matrix API
python -m uvicorn services.matrix.app:app --port 8000

# 2. Start recording (or manually drop MP4 files into recordings/raw/)
# OBS: set output to recordings/raw/, split every 5 min

# 3. Start ingester (chunks videos as they arrive)
python video/ingester.py

# 4. Start analyzer (captions and scores each clip)
python video/cosmos_analyzer.py

# 5. Browse at http://localhost:8000/video

# 6. Build a demo clip from top highlights
python video/short_builder.py --auto --top 5 --output demo_highlight_reel.mp4
```

---

## Linking Video to PLC Incidents

When a PLC fault occurs (e.g., conveyor jam), the system records the timestamp. The video analyzer can cross-reference this with clip timestamps to tag the relevant video segment. This creates a complete incident record:

- **PLC data**: what the sensors saw (motor current spike, photoeye blocked)
- **Cosmos insight**: root cause analysis (physical obstruction)
- **Video clip**: what actually happened (technician sees the jam)

All three appear together in the HMI incident detail view.

---

## Swapping in Real Cosmos Reason 2

The stub is in `cosmos/client.py → analyze_video()`. To use real Cosmos:

1. Set `NVIDIA_COSMOS_API_KEY` env var
2. Replace the stub in `analyze_video()` with an HTTP call to the Cosmos API
3. The video is sent as a URL or base64-encoded payload
4. Response format stays the same: `{caption, key_events, interesting_score}`

See `docs/cosmos_integration_stub.md` for the full swap guide.
