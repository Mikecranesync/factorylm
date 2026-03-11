#!/usr/bin/env bash
# FactoryLM Network Health Check — CHARLIE node
# Run: bash ~/factorylm/scripts/health-check.sh

set -uo pipefail

# Source master config
source ~/factorylm/config/network.env

PASS=0
FAIL=0

check() {
    local name="$1" url="$2"
    local code
    code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 3 "$url" 2>/dev/null || echo "000")
    if [[ "$code" =~ ^2 ]]; then
        printf "  %-20s %-40s HTTP %s\n" "$name" "$url" "$code"
        ((PASS++))
    else
        printf "  %-20s %-40s HTTP %s\n" "$name" "$url" "$code"
        ((FAIL++))
    fi
}

check_launchagent() {
    local label="$1"
    local pid
    pid=$(launchctl list "$label" 2>/dev/null | awk '/PID/ {print $3}')
    if [[ -n "$pid" && "$pid" != "-" && "$pid" != "0" ]]; then
        printf "  %-40s PID=%-8s\n" "$label" "$pid"
    else
        printf "  %-40s NOT RUNNING\n" "$label"
        ((FAIL++))
    fi
}

echo "=== FactoryLM Health Check $(date '+%Y-%m-%d %H:%M:%S') ==="
echo ""
echo "--- HTTP Services ---"
check "brain-ingest"   "http://${CHARLIE_TAILSCALE_IP}:${BRAIN_INGEST_PORT}/health"
check "brain-mcp"      "http://${CHARLIE_TAILSCALE_IP}:${BRAIN_MCP_PORT}/health"
check "cosmos-r2-vllm" "http://${CHARLIE_TAILSCALE_IP}:${VASTAI_TUNNEL_LOCAL_PORT}/v1/models"
check "ollama"         "http://${CHARLIE_TAILSCALE_IP}:${OLLAMA_PORT}/api/tags"

echo ""
echo "--- LaunchAgents ---"
check_launchagent "com.factorylm.brain-ingest"
check_launchagent "com.factorylm.brain-mcp"
check_launchagent "com.factorylm.vastai-tunnel"
check_launchagent "com.ollama"

echo ""
echo "--- Ports ---"
for port in $BRAIN_INGEST_PORT $BRAIN_MCP_PORT $VASTAI_TUNNEL_LOCAL_PORT $OLLAMA_PORT; do
    bound=$(lsof -i :"$port" 2>/dev/null | grep LISTEN | awk '{print $1, $9}' | head -1)
    if [[ -n "$bound" ]]; then
        printf "  :%s  %s\n" "$port" "$bound"
    else
        printf "  :%s  NOT BOUND\n" "$port"
    fi
done

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
[[ $FAIL -eq 0 ]] && exit 0 || exit 1
