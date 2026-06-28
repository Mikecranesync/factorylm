#!/usr/bin/env bash
# Mission Control — Record All 8 Promo Videos
#
# Runs the full pipeline (record → voice → merge) for every tab.
# auth.json must already exist: run node demo/login.mjs first.
#
# Usage (from apps/mission-control/):
#   TTS_PROVIDER=macos bash demo/run_all.sh
#   TTS_PROVIDER=elevenlabs bash demo/run_all.sh
#
# To re-run a single tab:
#   node demo/record_tab.mjs 02_dashboard
#   TTS_PROVIDER=macos python demo/voice.py --tab 02_dashboard
#   bash demo/sync_tab.sh 02_dashboard

set -euo pipefail

DEMO_DIR="$(cd "$(dirname "$0")" && pwd)"
PROVIDER=${TTS_PROVIDER:-macos}

TABS=(
  "01_chat_relay"
  "02_dashboard"
  "03_terminal"
  "04_worker_swarm"
  "05_ralph_loop"
  "06_agents"
  "07_tools"
  "08_hub"
)

if [ ! -f "$DEMO_DIR/auth.json" ]; then
  echo "ERROR: demo/auth.json not found."
  echo "       Run: HUB_EMAIL=x HUB_PASSWORD=y node demo/login.mjs"
  exit 1
fi

echo "Mission Control — Recording All 8 Promo Videos"
echo "TTS Provider: $PROVIDER"
echo "Tabs: ${#TABS[@]}"
echo ""

FAILED=()

for SLUG in "${TABS[@]}"; do
  echo "========================================"
  echo "  TAB: $SLUG"
  echo "========================================"

  # 1. Record
  echo "  [1/3] Recording UI …"
  if ! node "$DEMO_DIR/record_tab.mjs" "$SLUG"; then
    echo "  ERROR: Recording failed for $SLUG"
    FAILED+=("$SLUG:record")
    continue
  fi

  # 2. Voice
  echo "  [2/3] Generating narration …"
  if ! TTS_PROVIDER=$PROVIDER /usr/bin/python3 "$DEMO_DIR/voice.py" --tab "$SLUG"; then
    echo "  ERROR: Voice generation failed for $SLUG"
    FAILED+=("$SLUG:voice")
    continue
  fi

  # 3. Merge
  echo "  [3/3] Merging A/V …"
  if ! bash "$DEMO_DIR/sync_tab.sh" "$SLUG"; then
    echo "  ERROR: Merge failed for $SLUG"
    FAILED+=("$SLUG:sync")
    continue
  fi

  NAME="${SLUG#*_}"
  echo "  → demo/tabs/$SLUG/${NAME}.mp4"
  echo ""
done

echo "========================================"
echo "DONE"
echo ""

# List all outputs
echo "Output files:"
for SLUG in "${TABS[@]}"; do
  NAME="${SLUG#*_}"
  MP4="$DEMO_DIR/tabs/$SLUG/${NAME}.mp4"
  if [ -f "$MP4" ]; then
    DUR=$(ffprobe -v quiet -show_entries format=duration -of "csv=p=0" "$MP4" 2>/dev/null | xargs printf "%.0fs" 2>/dev/null || echo "?")
    echo "  ✓ $MP4 ($DUR)"
  else
    echo "  ✗ $MP4 (missing)"
  fi
done

if [ ${#FAILED[@]} -gt 0 ]; then
  echo ""
  echo "FAILED: ${FAILED[*]}"
  exit 1
fi
