#!/bin/bash
# PEPPER Doppler Setup Script
# Sets up secrets management with Doppler

set -e

PROJECT="voltron"
CONFIG="dev"

echo "=========================================="
echo "PEPPER Doppler Setup"
echo "=========================================="
echo ""

# Check Doppler CLI
if ! command -v doppler &> /dev/null; then
    echo "❌ Doppler CLI not installed"
    echo "   Install: curl -Ls https://cli.doppler.com/install.sh | sh"
    exit 1
fi

echo "✓ Doppler CLI found"

# Check login
if ! doppler whoami &> /dev/null; then
    echo "❌ Not logged in to Doppler"
    echo "   Run: doppler login"
    exit 1
fi

echo "✓ Logged in to Doppler"

# Check project access
if ! doppler secrets --project "$PROJECT" --config "$CONFIG" &> /dev/null; then
    echo "❌ Cannot access project: $PROJECT/$CONFIG"
    exit 1
fi

echo "✓ Project access confirmed: $PROJECT/$CONFIG"
echo ""

# List current secrets
echo "Current secrets in $PROJECT/$CONFIG:"
echo "----------------------------------------"
doppler secrets --project "$PROJECT" --config "$CONFIG" --only-names

echo ""
echo "=========================================="
echo "Required Secrets for PEPPER"
echo "=========================================="

# Required secrets
REQUIRED=(
    "PEPPER_PRIME_TOKEN:Telegram bot token for God Mode (@Spicyclawd_bot)"
    "GROQ_API_KEY:Groq API key for Layer 2 LLM"
)

# Optional secrets
OPTIONAL=(
    "FACTORYLM_BOT_TOKEN:Telegram bot token for Demo Mode (optional)"
    "ANTHROPIC_API_KEY:Claude API key for Layer 3 fallback"
    "HONEYCOMB_API_KEY:Observability (optional)"
    "SENTRY_DSN:Error tracking (optional)"
)

echo ""
echo "REQUIRED:"
for item in "${REQUIRED[@]}"; do
    KEY="${item%%:*}"
    DESC="${item#*:}"
    VALUE=$(doppler secrets get "$KEY" --project "$PROJECT" --config "$CONFIG" --plain 2>/dev/null || echo "")
    if [ -n "$VALUE" ]; then
        echo "  ✓ $KEY - $DESC"
    else
        echo "  ❌ $KEY - $DESC [MISSING]"
    fi
done

echo ""
echo "OPTIONAL:"
for item in "${OPTIONAL[@]}"; do
    KEY="${item%%:*}"
    DESC="${item#*:}"
    VALUE=$(doppler secrets get "$KEY" --project "$PROJECT" --config "$CONFIG" --plain 2>/dev/null || echo "")
    if [ -n "$VALUE" ]; then
        echo "  ✓ $KEY - $DESC"
    else
        echo "  ○ $KEY - $DESC [not set]"
    fi
done

echo ""
echo "=========================================="
echo "Setup Commands"
echo "=========================================="
echo ""
echo "To add missing secrets:"
echo ""
echo "  # Add bot token"
echo "  doppler secrets set PEPPER_PRIME_TOKEN='your_token' --project $PROJECT --config $CONFIG"
echo ""
echo "  # Add Groq API key"
echo "  doppler secrets set GROQ_API_KEY='gsk_...' --project $PROJECT --config $CONFIG"
echo ""
echo "  # Add Anthropic API key (optional)"
echo "  doppler secrets set ANTHROPIC_API_KEY='sk-ant-...' --project $PROJECT --config $CONFIG"
echo ""
echo "=========================================="
echo "Running PEPPER with Doppler"
echo "=========================================="
echo ""
echo "  # Run gateway with Doppler injection"
echo "  doppler run --project $PROJECT --config $CONFIG -- python -m pepper.gateway"
echo ""
echo "  # Or set up automatic injection"
echo "  doppler setup --project $PROJECT --config $CONFIG"
echo ""
