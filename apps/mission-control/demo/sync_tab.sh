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

# Output length follows the AUDIO (narration), not the recorded video. tpad clones
# the last video frame so a longer narration is never truncated; -t trims to the
# audio length so a shorter narration leaves no dangling silent video. This makes
# A/V drift ~0 for any TTS provider (incl. a voice swap that changes audio length).
# loudnorm normalizes the voice to -16 LUFS / -1 dBTP (rubric dimension 2).
ADUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$AUDIO_FILE")

echo "Video : $WEBM"
echo "Audio : $AUDIO_FILE (${ADUR}s — drives output length)"
echo "Output: $OUT"

ffmpeg -y \
  -i "$WEBM" \
  -i "$AUDIO_FILE" \
  -filter_complex "[0:v]tpad=stop_mode=clone:stop_duration=3600[vp];[1:a]loudnorm=I=-16:TP=-1:LRA=11[ap]" \
  -map "[vp]" -map "[ap]" \
  -c:v libx264 -preset fast -crf 18 \
  -c:a aac -b:a 192k \
  -t "$ADUR" \
  "$OUT"

echo ""
echo "Done → $OUT"
ffprobe -v quiet -show_entries format=duration -of "csv=p=0" "$OUT" 2>/dev/null \
  | xargs -I{} printf "Duration: %.1fs\n" {}
