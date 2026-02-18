#!/bin/bash
# ============================================================================
# Upload secrets to Doppler from .env.doppler
# ============================================================================
# Usage:
#   1. Edit .env.doppler with your real API keys
#   2. Run: ./upload_secrets.sh
#   3. Delete .env.doppler (secrets are now in Doppler!)
# ============================================================================

set -e

ENV_FILE=".env.doppler"
PROJECT="voltron"
CONFIG="dev"

echo "=============================================="
echo "  PEPPER POTTS - Doppler Secret Upload"
echo "=============================================="

# Check if file exists
if [ ! -f "$ENV_FILE" ]; then
    echo "ERROR: $ENV_FILE not found!"
    echo "Create it first with your API keys."
    exit 1
fi

# Check for placeholder values
if grep -q "YOUR_.*_HERE" "$ENV_FILE"; then
    echo ""
    echo "WARNING: Found placeholder values in $ENV_FILE"
    echo "Please replace these with your actual API keys:"
    grep "YOUR_.*_HERE" "$ENV_FILE" | head -10
    echo ""
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Upload to Doppler
echo ""
echo "Uploading secrets to Doppler..."
echo "  Project: $PROJECT"
echo "  Config:  $CONFIG"
echo ""

doppler secrets upload "$ENV_FILE" --project "$PROJECT" --config "$CONFIG"

echo ""
echo "=============================================="
echo "  Upload Complete!"
echo "=============================================="
echo ""
echo "Next steps:"
echo "  1. Verify: doppler secrets --project $PROJECT --config $CONFIG"
echo "  2. Delete: rm $ENV_FILE"
echo "  3. Run bot: doppler run --project $PROJECT --config $CONFIG -- python run.py"
echo ""
