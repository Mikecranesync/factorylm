#!/usr/bin/env bash
# Mission Control — Per-Tab A/V Merge
#
# Usage (from apps/mission-control/):
#   bash demo/sync_tab.sh <slug>
#
# Example:
#   bash demo/sync_tab.sh 01_chat_relay
#   → demo/tabs/01_chat_relay/chat_relay.mp4

set -euo pipefail

SLUG=${1:?Usage: bash demo/sync_tab.sh <slug>}
DEMO_DIR="$(cd "$(dirname "$0")" && pwd)"
TAB_DIR="$DEMO_DIR/tabs/$SLUG"

if [ ! -d "$TAB_DIR" ]; then
  echo "ERROR: Tab directory not found: $TAB_DIR"
  exit 1
fi

AUDIO_FILE="$TAB_DIR/audio/full_narration.mp3"
if [ ! -f "$AUDIO_FILE" ]; then
  echo "ERROR: Audio not found: $AUDIO_FILE"
  echo "       Run: TTS_PROVIDER=macos python demo/voice.py --tab $SLUG"
  exit 1
fi

# Pick most recent webm in tab's raw/ dir
WEBM=$(ls -t "$TAB_DIR/raw/"*.webm 2>/dev/null | head -1)
if [ -z "$WEBM" ]; then
  echo "ERROR: No webm found in $TAB_DIR/raw/"
  echo "       Run: node demo/record_tab.mjs $SLUG"
  exit 1
fi

# Output filename: strip the NN_ prefix (e.g. 01_chat_relay → chat_relay.mp4)
NAME="${SLUG#*_}"
OUT="$TAB_DIR/${NAME}.mp4"

echo "Video : $WEBM"
echo "Audio : $AUDIO_FILE"
echo "Output: $OUT"

ffmpeg -y \
  -i "$WEBM" \
  -i "$AUDIO_FILE" \
  -c:v libx264 -preset fast -crf 18 \
  -c:a aac -b:a 192k \
  -shortest \
  "$OUT"

echo ""
echo "Done → $OUT"
ffprobe -v quiet -show_entries format=duration -of "csv=p=0" "$OUT" 2>/dev/null \
  | xargs -I{} printf "Duration: %.1fs\n" {}
