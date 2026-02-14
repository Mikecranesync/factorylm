# Video Pipeline

**Last Updated:** 2026-02-13  
**Status:** Working — stub analysis, real ffmpeg chunking

---

## Overview

The video pipeline ingests continuous camera footage (or screen recordings from Factory I/O), chunks it into clips, analyzes each clip via Cosmos Reason 2, and surfaces highlights for demos and documentation.

```
Camera / Screen Recording
        │ drops files into recordings/raw/
        ▼
  video/ingester.py
        │ ffmpeg chunks → recordings/chunks/
        │ registers clips in Matrix DB
        ▼
  video/cosmos_analyzer.py
        │ polls for pending clips
        │ calls CosmosClient.analyze_video()
        │ stores captions + scores
        │ marks highlights (score ≥ 60)
        ▼
  video/highlight_selector.py
        │ queries highlights by date/event/score
        ▼
  video/short_builder.py
        │ concatenates clips with ffmpeg
        │ optional title overlay
        ▼
  Demo Video (30-60 second MP4)
```

---

## Setup

### Prerequisites
- **ffmpeg** installed and on PATH (check: `ffmpeg -version`)
- Python packages: `httpx` (already installed)
- Matrix API running at http://localhost:8000

### Start Continuous Recording

Use any screen recording tool:

**OBS Studio (recommended):**
1. Set output directory to `recordings/raw/`
2. Set recording format to MP4
3. Set "File Splitting" to split every 5 minutes
4. Start recording

**ffmpeg command line:**
```bash
# Record screen (Windows, 5-minute segments)
ffmpeg -f gdigrab -framerate 10 -i desktop -t 300 -c:v libx264 -preset ultrafast recordings/raw/screen_%03d.mp4

# Record webcam (Linux)
ffmpeg -f v4l2 -framerate 15 -i /dev/video0 -t 300 -c:v libx264 -preset ultrafast recordings/raw/cam_%03d.mp4
```

---

## Usage

### 1. Start the Ingester

```bash
python video/ingester.py --input recordings/raw --chunk-duration 15
```

Watches `recordings/raw/` for new video files, chunks them into 15-second clips, and registers each in the Matrix API.

### 2. Start the Analyzer

```bash
python video/cosmos_analyzer.py --interval 10
```

Polls for unanalyzed clips every 10 seconds, runs Cosmos analysis (stub), and marks interesting clips as highlights.

### 3. Find Highlights

```bash
# Top 5 highlights
python video/highlight_selector.py --top 5

# Filter by date and keyword
python video/highlight_selector.py --date 2026-02-13 --event jam

# Only high-scoring clips
python video/highlight_selector.py --min-score 80
```

### 4. Build a Demo Video

```bash
# From specific clip IDs
python video/short_builder.py --clips 1,5,12 --output demo.mp4 --title "Conveyor Jam Diagnosis"

# Auto-select top highlights
python video/short_builder.py --auto --top 5 --output best_of.mp4
```

---

## Configuration

See `config/video.yaml`:

| Setting | Default | Description |
|---------|---------|-------------|
| `chunk_duration_seconds` | 15 | Length of each clip |
| `interesting_threshold` | 60 | Score above this = highlight |
| `input_dir` | recordings/raw | Where raw videos land |
| `chunks_dir` | recordings/chunks | Where clips are stored |
| `ingester_poll_seconds` | 5 | How often to check for new files |
| `analyzer_poll_seconds` | 10 | How often to check for pending clips |

---

## Web HMI

The Video Log page at **http://localhost:8000/video** shows:
- All clips with status, score, and caption snippet
- Click any clip for full analysis detail
- Filter by status (pending, analyzed, highlight)
- Auto-refreshes every 5 seconds

---

## Clip Status Lifecycle

```
pending_analysis → analyzed (score < threshold)
                 → highlight (score ≥ threshold)
                 → archived (manually or after use)
```
