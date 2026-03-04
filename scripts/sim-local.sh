#!/usr/bin/env bash
#
# FactoryLM Local Simulation
# Starts plc-modbus (mock mode) + diagnosis service + opens dashboard.
#
# Usage:  bash scripts/sim-local.sh
# Stop:   Ctrl+C (kills both services)
#
set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PLC_PORT=8001
DIAG_PORT=8200

echo "=== FactoryLM Local Simulation ==="
echo "    plc-modbus (mock)  → http://localhost:$PLC_PORT"
echo "    diagnosis service  → http://localhost:$DIAG_PORT"
echo "    sim dashboard      → http://localhost:$DIAG_PORT/sim"
echo ""

# Cleanup on exit
cleanup() {
  echo ""
  echo "Shutting down..."
  kill $PLC_PID $DIAG_PID 2>/dev/null || true
  exit 0
}
trap cleanup INT TERM

# 1. Start plc-modbus in mock mode
echo "[1/2] Starting plc-modbus (mock mode) on :$PLC_PORT..."
cd "$REPO_ROOT/services/plc-modbus"
FACTORYLM_MOCK_MODE=true python -m uvicorn backend.main:app \
  --host 0.0.0.0 --port $PLC_PORT --log-level info &
PLC_PID=$!

# Wait for it to be ready
for i in {1..10}; do
  sleep 1
  if curl -s "http://localhost:$PLC_PORT/api/plc/status" >/dev/null 2>&1; then
    echo "    plc-modbus ready (PID $PLC_PID)"
    break
  fi
  [ $i -eq 10 ] && echo "    WARNING: plc-modbus may not be ready yet"
done

# 2. Start diagnosis service
echo "[2/2] Starting diagnosis service on :$DIAG_PORT..."
cd "$REPO_ROOT/services/diagnosis"
PLC_MODBUS_URL="http://localhost:$PLC_PORT" \
  LLM_ROUTER_URL="http://localhost:8100" \
  python -m uvicorn main:app \
  --host 0.0.0.0 --port $DIAG_PORT --log-level info &
DIAG_PID=$!

sleep 2
echo ""
echo "=== READY ==="
echo ""
echo "  Dashboard:  http://localhost:$DIAG_PORT/sim"
echo "  PLC I/O:    http://localhost:$PLC_PORT/api/plc/io"
echo "  Diagnose:   curl -X POST http://localhost:$DIAG_PORT/diagnose \\"
echo "                -H 'Content-Type: application/json' \\"
echo "                -d '{\"question\": \"What is the machine status?\"}'"
echo ""
echo "Press Ctrl+C to stop."
wait
