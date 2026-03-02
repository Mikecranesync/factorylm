#!/usr/bin/env bash
# verify-pi-factory.sh — Post-install smoke test for Pi Factory appliance
# Run on the Pi after setup-pi-factory.sh completes.
set -euo pipefail

PASS=0
FAIL=0

check() {
    local label="$1"
    shift
    if "$@" > /dev/null 2>&1; then
        echo "  [PASS] $label"
        PASS=$((PASS + 1))
    else
        echo "  [FAIL] $label"
        FAIL=$((FAIL + 1))
    fi
}

echo "=== Pi Factory Verification ==="
echo ""

# 1. eth0 has a usable IP (DHCP 192.x or link-local 169.254.x)
echo "Network:"
check "eth0 has IPv4 address" \
    bash -c 'ip addr show eth0 | grep -qE "inet (192|10|172|169\.254)\."'

# 2. Hostname
echo "Hostname:"
check "hostname is pi-factory" \
    test "$(hostname)" = "pi-factory"

# 3. Avahi
echo "Avahi:"
check "avahi-daemon is running" \
    systemctl is-active avahi-daemon
check "pi-factory service file exists" \
    test -f /etc/avahi/services/pi-factory.service

# 4. Systemd service
echo "Service:"
check "pi-factory.service is enabled" \
    systemctl is-enabled pi-factory
check "pi-factory.service is running" \
    systemctl is-active pi-factory

# 5. Health endpoint
echo "Health:"
check "GET /api/health returns 200" \
    curl -sf http://localhost:8000/api/health

# 6. Netplan config
echo "Netplan:"
check "/etc/netplan/99-pi-factory.yaml exists" \
    test -f /etc/netplan/99-pi-factory.yaml

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="

if [ "$FAIL" -gt 0 ]; then
    exit 1
fi
