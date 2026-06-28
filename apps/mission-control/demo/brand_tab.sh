#!/usr/bin/env bash
# Mission Control — Add Branded Intro/Outro to a Tab
#
# Renders brand cards (make_cards.mjs) and concatenates intro + tab + outro,
# normalizing res/fps/sar/sample-rate so the concat is reliable. Writes a
# *_branded.mp4 next to the clean one (non-destructive).
#
# Usage (from apps/mission-control/):  bash demo/brand_tab.sh <slug>

set -euo pipefail
SLUG=${1:?Usage: bash demo/brand_tab.sh <slug>}
DEMO_DIR="$(cd "$(dirname "$0")" && pwd)"
TAB_DIR="$DEMO_DIR/tabs/$SLUG"
NAME="${SLUG#*_}"
MAIN="$TAB_DIR/${NAME}.mp4"
BRAND="$TAB_DIR/brand"
OUT="$TAB_DIR/${NAME}_branded.mp4"

[ -f "$MAIN" ] || { echo "ERROR: $MAIN not found (run sync_tab.sh first)"; exit 1; }

# 1. Render the brand cards (Playwright → PNG; this ffmpeg has no drawtext)
node "$DEMO_DIR/make_cards.mjs" "$SLUG"

# 2. Concat: intro card (3s) + tab + outro card (2.5s). Each input is forced to
#    1920x1080 / 25fps / sar 1 / 48kHz so concat never mismatches.
ffmpeg -y \
  -loop 1 -t 3   -i "$BRAND/intro.png" \
  -i "$MAIN" \
  -loop 1 -t 2.5 -i "$BRAND/outro.png" \
  -f lavfi -t 3   -i anullsrc=r=48000:cl=stereo \
  -f lavfi -t 2.5 -i anullsrc=r=48000:cl=stereo \
  -filter_complex "[0:v]scale=1920:1080,fps=25,setsar=1,fade=t=in:st=0:d=0.4,fade=t=out:st=2.6:d=0.4,format=yuv420p[v0];[1:v]scale=1920:1080,fps=25,setsar=1,format=yuv420p[v1];[2:v]scale=1920:1080,fps=25,setsar=1,fade=t=in:st=0:d=0.3,format=yuv420p[v2];[3:a]aresample=48000[a0];[1:a]aresample=48000[a1];[4:a]aresample=48000[a2];[v0][a0][v1][a1][v2][a2]concat=n=3:v=1:a=1[v][a]" \
  -map "[v]" -map "[a]" \
  -c:v libx264 -preset fast -crf 18 -c:a aac -b:a 192k \
  "$OUT"

echo "Done → $OUT"
ffprobe -v error -show_entries format=duration -of csv=p=0 "$OUT" | xargs printf "Duration: %.1fs\n"
