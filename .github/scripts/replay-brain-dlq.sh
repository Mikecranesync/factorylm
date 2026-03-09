#!/usr/bin/env bash
# Replay dead-letter brain-feed payloads from GitHub Actions artifacts.
# Usage: BRAIN_INGEST_URL=... GH_TOKEN=... bash replay-brain-dlq.sh [repo]
set -euo pipefail

REPO="${1:-Mikecranesync/factorylm}"
BRAIN_URL="${BRAIN_INGEST_URL:?BRAIN_INGEST_URL required}"

echo "=== Brain DLQ Replay ==="
echo "Repo: $REPO"

# Health check first
BASE_URL=$(echo "$BRAIN_URL" | sed 's|/ingest$||')
HTTP=$(curl -s -o /dev/null -w '%{http_code}' \
  --connect-timeout 5 --max-time 10 "${BASE_URL}/health" || echo "000")
if [ "$HTTP" = "000" ] || [ "$HTTP" -ge 400 ] 2>/dev/null; then
  echo "ERROR: Brain ingest not healthy (HTTP $HTTP). Aborting replay."
  exit 1
fi
echo "Brain ingest healthy (HTTP $HTTP)"

# List DLQ artifacts
ARTIFACTS=$(gh api "repos/$REPO/actions/artifacts" \
  --jq '.artifacts[] | select(.name | startswith("brain-dlq-")) | .id' \
  2>/dev/null || echo "")

COUNT=$(echo "$ARTIFACTS" | grep -c . 2>/dev/null || echo "0")
echo "Found $COUNT DLQ artifacts"

for AID in $ARTIFACTS; do
  echo "  Replaying artifact $AID..."
  gh api "repos/$REPO/actions/artifacts/$AID/zip" > /tmp/dlq.zip
  unzip -o /tmp/dlq.zip -d /tmp/dlq-extract > /dev/null
  if [ -f /tmp/dlq-extract/payload.json ]; then
    RESULT=$(curl -s -o /dev/null -w '%{http_code}' \
      --connect-timeout 5 --max-time 10 \
      -X POST "$BRAIN_URL" -H "Content-Type: application/json" \
      -d @/tmp/dlq-extract/payload.json || echo "000")
    echo "    HTTP $RESULT"
    if [ "$RESULT" -lt 400 ] 2>/dev/null; then
      gh api -X DELETE "repos/$REPO/actions/artifacts/$AID" 2>/dev/null || true
      echo "    Replayed + deleted artifact"
    fi
  fi
  rm -rf /tmp/dlq.zip /tmp/dlq-extract
done
echo "=== Replay complete ==="
