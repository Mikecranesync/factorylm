#!/usr/bin/env bash
# setup-vps.sh — Configure Honeycomb OpenTelemetry for an openclaw VPS instance
#
# Usage:
#   bash setup-vps.sh \
#     --instance-name ultron \
#     --api-key hcaik_xxxxxxxxxxxx \
#     --service-name openclaw
#
#   bash setup-vps.sh \
#     --instance-name jarvis-legacy \
#     --api-key hcaik_xxxxxxxxxxxx \
#     --service-name clawdbot
#
set -euo pipefail

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------
INSTANCE_NAME=""
API_KEY=""
SERVICE_NAME=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --instance-name) INSTANCE_NAME="$2"; shift 2 ;;
    --api-key)       API_KEY="$2";       shift 2 ;;
    --service-name)  SERVICE_NAME="$2";  shift 2 ;;
    *) echo "Unknown arg: $1"; exit 1 ;;
  esac
done

if [[ -z "$INSTANCE_NAME" || -z "$API_KEY" || -z "$SERVICE_NAME" ]]; then
  echo "Usage: $0 --instance-name <name> --api-key <key> --service-name <openclaw|clawdbot>"
  exit 1
fi

OTEL_SERVICE="openclaw-${INSTANCE_NAME}"
TRACING_SRC="$(cd "$(dirname "$0")" && pwd)/tracing.js"
TRACING_DEST="/root/.openclaw/tracing.js"
SYSTEMD_UNIT="/etc/systemd/system/${SERVICE_NAME}.service"
ENDPOINT="https://api.honeycomb.io:443"

echo "=== Honeycomb OTel Setup for ${INSTANCE_NAME} ==="
echo "  Service name : ${OTEL_SERVICE}"
echo "  systemd unit : ${SYSTEMD_UNIT}"
echo "  Tracing file : ${TRACING_DEST}"
echo ""

# ---------------------------------------------------------------------------
# Step 1: Copy tracing.js
# ---------------------------------------------------------------------------
echo "[1/4] Copying tracing.js → ${TRACING_DEST}"
mkdir -p /root/.openclaw
cp "${TRACING_SRC}" "${TRACING_DEST}"
chmod 644 "${TRACING_DEST}"
echo "  ✓ done"
echo ""

# ---------------------------------------------------------------------------
# Step 2: Install OTel npm packages globally
# ---------------------------------------------------------------------------
echo "[2/4] Installing OpenTelemetry npm packages globally..."
bash "$(dirname "$0")/install-deps.sh"
echo ""

# ---------------------------------------------------------------------------
# Step 3: Patch systemd service — add Environment lines
# ---------------------------------------------------------------------------
echo "[3/4] Updating systemd unit ${SYSTEMD_UNIT}"

if [[ ! -f "${SYSTEMD_UNIT}" ]]; then
  echo "  ERROR: ${SYSTEMD_UNIT} not found. Check --service-name."
  exit 1
fi

# Back up original
cp "${SYSTEMD_UNIT}" "${SYSTEMD_UNIT}.bak.$(date +%s)"

# Remove any previous OTel / Honeycomb environment lines we may have added
sed -i '/^Environment=.*HONEYCOMB_API_KEY/d'              "${SYSTEMD_UNIT}"
sed -i '/^Environment=.*OTEL_SERVICE_NAME/d'              "${SYSTEMD_UNIT}"
sed -i '/^Environment=.*OTEL_EXPORTER_OTLP_ENDPOINT/d'   "${SYSTEMD_UNIT}"
sed -i '/^Environment=.*OTEL_EXPORTER_OTLP_PROTOCOL/d'   "${SYSTEMD_UNIT}"
sed -i '/^Environment=.*OTEL_EXPORTER_OTLP_HEADERS/d'    "${SYSTEMD_UNIT}"
sed -i '/^Environment=.*OTEL_INSTANCE_NAME/d'             "${SYSTEMD_UNIT}"
sed -i '/^Environment=.*OTEL_DEPLOYMENT_ENVIRONMENT/d'    "${SYSTEMD_UNIT}"
# Remove existing NODE_OPTIONS line (we'll re-add with tracing)
sed -i '/^Environment=.*NODE_OPTIONS.*tracing/d'          "${SYSTEMD_UNIT}"

# Build the Environment block
ENV_BLOCK=$(cat <<EOF
Environment=HONEYCOMB_API_KEY=${API_KEY}
Environment=OTEL_SERVICE_NAME=${OTEL_SERVICE}
Environment=OTEL_EXPORTER_OTLP_ENDPOINT=${ENDPOINT}
Environment=OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
Environment=OTEL_EXPORTER_OTLP_HEADERS=x-honeycomb-team=${API_KEY}
Environment=OTEL_INSTANCE_NAME=${INSTANCE_NAME}
Environment=OTEL_DEPLOYMENT_ENVIRONMENT=production
Environment=NODE_OPTIONS=-r ${TRACING_DEST}
EOF
)

# Insert after the [Service] line
sed -i "/^\[Service\]/a\\
${ENV_BLOCK}" "${SYSTEMD_UNIT}"

echo "  ✓ Environment variables injected"
echo ""

# ---------------------------------------------------------------------------
# Step 4: Reload and restart
# ---------------------------------------------------------------------------
echo "[4/4] Reloading systemd and restarting ${SERVICE_NAME}..."
systemctl daemon-reload
systemctl restart "${SERVICE_NAME}"
echo "  ✓ Service restarted"
echo ""

# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------
echo "========================================="
echo "  SETUP COMPLETE — Verify it's working"
echo "========================================="
echo ""
echo "1. Check service status:"
echo "   systemctl status ${SERVICE_NAME}"
echo ""
echo "2. Check logs for tracing init message:"
echo "   journalctl -u ${SERVICE_NAME} --no-pager -n 30 | grep tracing"
echo "   → Should see: [tracing] ✓  OpenTelemetry started → ${ENDPOINT}"
echo ""
echo "3. Send a test message to the bot, then check Honeycomb:"
echo "   https://ui.honeycomb.io → Dataset: ${OTEL_SERVICE}"
echo ""
echo "4. If no data appears after 2 min, check:"
echo "   - API key is valid (starts with hcaik_)"
echo "   - Outbound HTTPS to api.honeycomb.io is not blocked"
echo "   - journalctl -u ${SERVICE_NAME} -f  (look for errors)"
echo ""
