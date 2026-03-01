#!/bin/bash
# Cron wrapper for commit note enrichment.
# Pulls the latest vault, runs enrichment, then pushes changes.
set -euo pipefail

VAULT_DIR="/Users/factorylm/FactoryLM_OS"
WORKER_DIR="/Users/factorylm/factorylm/workers"
LOG="/tmp/enrichment-cron.log"

exec >> "$LOG" 2>&1
echo "=== $(date -u '+%Y-%m-%d %H:%M:%S UTC') === Starting enrichment ==="

# Pull latest vault (sync script may have pushed new notes)
cd "$VAULT_DIR"
git pull --rebase --quiet origin main 2>/dev/null || true

# Get GROQ_API_KEY from Doppler
export GROQ_API_KEY
GROQ_API_KEY=$(doppler secrets get GROQ_API_KEY --plain 2>/dev/null)

if [ -z "$GROQ_API_KEY" ]; then
    echo "ERROR: Could not get GROQ_API_KEY from Doppler"
    exit 1
fi

# Run enrichment on today's notes (and yesterday's in case of timezone lag)
cd "$WORKER_DIR"
TODAY=$(date -u '+%Y-%m-%d')
YESTERDAY=$(date -u -v-1d '+%Y-%m-%d')

python3 run_enrichment.py --day "$TODAY" || true
python3 run_enrichment.py --day "$YESTERDAY" || true

# Push enriched notes back to vault
cd "$VAULT_DIR"
if [ -n "$(git status --porcelain 10_Commit_Notes/)" ]; then
    git add 10_Commit_Notes/
    git commit -m "enrich: AI summaries for $TODAY" --author="factorylm-bot <bot@factorylm.com>"
    git push origin main
    echo "Pushed enriched notes"
else
    echo "No changes to push"
fi

echo "=== Done ==="
