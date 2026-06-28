#!/usr/bin/env bash
# Mission Control Demo — A/V Sync
#
# Merges the Playwright webm recording with the TTS narration track
# into a final polished MP4.
#
# Usage (from repo root):
#   bash apps/mission-control/demo/sync.sh
#
# Prerequisites:
#   ffmpeg installed (brew install ffmpeg)
#   demo/raw/*.webm  — produced by record.mjs
#   demo/audio/full_narration.mp3 — produced by voice.py

set -euo pipefail

DEMO_DIR="$(cd "$(dirname "$0")" && pwd)"
RAW_DIR="$DEMO_DIR/raw"
AUDIO_FILE="$DEMO_DIR/audio/full_narration.mp3"
OUT_FILE="$DEMO_DIR/final_demo.mp4"

# --- Validate inputs ---

if [ ! -d "$RAW_DIR" ] || [ -z "$(ls -A "$RAW_DIR"/*.webm 2>/dev/null)" ]; then
  echo "ERROR: No webm files found in $RAW_DIR"
  echo "       Run: node apps/mission-control/demo/record.mjs"
  exit 1
fi

if [ ! -f "$AUDIO_FILE" ]; then
  echo "ERROR: Audio not found: $AUDIO_FILE"
  echo "       Run: TTS_PROVIDER=macos python apps/mission-control/demo/voice.py"
  exit 1
fi

# Pick the most recently modified webm (Playwright names them by context ID)
LATEST_WEBM=$(ls -t "$RAW_DIR"/*.webm | head -1)
echo "Video : $LATEST_WEBM"
echo "Audio : $AUDIO_FILE"
echo "Output: $OUT_FILE"
echo ""

# --- Merge ---

ffmpeg -y \
  -i "$LATEST_WEBM" \
  -i "$AUDIO_FILE" \
  -c:v libx264 -preset fast -crf 18 \
  -c:a aac -b:a 192k \
  -shortest \
  "$OUT_FILE"

echo ""
echo "Done → $OUT_FILE"

# Print duration info
ffprobe -v quiet -show_entries format=duration \
  -of "csv=p=0" "$OUT_FILE" 2>/dev/null \
  | xargs -I{} echo "Duration: {}s"
