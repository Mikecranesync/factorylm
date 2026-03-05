#!/usr/bin/env bash
# ============================================================
# Pi-Factory Verification Script
# Run these commands AFTER completing CCW setup (Parts A-E)
# ============================================================

set -e

PLC_IP="192.168.1.100"
PI_HOST="pi@pi-factory.local"
VENV="~/factorylm-cosmos-cookoff/.venv/bin/python3"
READER="~/factorylm-cosmos-cookoff/tools/plc_live_reader.py"

echo "=== Step 1: Check pi-factory is reachable ==="
ssh "$PI_HOST" "hostname -I"
echo ""

echo "=== Step 2: Ping PLC from pi-factory ==="
ssh "$PI_HOST" "ping -c 3 $PLC_IP"
echo ""

echo "=== Step 3: Read PLC tags via pylogix ==="
echo "(Ctrl+C to stop)"
ssh "$PI_HOST" "$VENV $READER --host $PLC_IP"
