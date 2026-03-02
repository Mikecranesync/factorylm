#!/usr/bin/env bash
# setup-pi-factory.sh — Zero-config install for Pi Factory PLC Discovery
# Run on a Raspberry Pi: curl <url> | bash  or  bash deploy/setup-pi-factory.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
INSTALL_DIR="${1:-/home/pi/factorylm/services/plc-modbus}"
VENV_DIR="$INSTALL_DIR/.venv"

echo "=== Pi Factory Setup ==="
echo "Install dir: $INSTALL_DIR"

# --- 1. System packages ---
echo "[1/6] Installing system packages..."
sudo apt-get update -qq
sudo apt-get install -y -qq avahi-daemon avahi-utils python3 python3-venv python3-pip net-tools

# --- 2. Hostname ---
echo "[2/6] Setting hostname to pi-factory..."
CURRENT_HOSTNAME=$(hostname)
if [ "$CURRENT_HOSTNAME" != "pi-factory" ]; then
    sudo hostnamectl set-hostname pi-factory
    # Update /etc/hosts
    sudo sed -i "s/127\.0\.1\.1.*$CURRENT_HOSTNAME/127.0.1.1\tpi-factory/" /etc/hosts
    echo "Hostname changed: $CURRENT_HOSTNAME -> pi-factory"
else
    echo "Hostname already set to pi-factory"
fi

# --- 3. DHCP with link-local fallback ---
echo "[3/6] Configuring network (Netplan: DHCP + link-local fallback)..."
NETPLAN_FILE="/etc/netplan/99-pi-factory.yaml"
sudo tee "$NETPLAN_FILE" > /dev/null <<'NETPLAN_EOF'
network:
  version: 2
  renderer: networkd
  ethernets:
    eth0:
      dhcp4: true
      dhcp4-overrides:
        route-metric: 100
      link-local: [ipv4]
      optional: true
NETPLAN_EOF
sudo chmod 600 "$NETPLAN_FILE"
sudo netplan apply
echo "Netplan configured: DHCP primary + link-local fallback on eth0"

# --- 4. Avahi mDNS ---
echo "[4/6] Installing Avahi service definition..."
sudo cp "$SCRIPT_DIR/avahi-pi-factory.service" /etc/avahi/services/pi-factory.service
sudo systemctl enable avahi-daemon
sudo systemctl restart avahi-daemon
echo "Avahi: pi-factory.local + _factorylm._tcp registered"

# --- 5. Python venv + deps ---
echo "[5/6] Setting up Python environment..."
if [ ! -d "$INSTALL_DIR" ]; then
    mkdir -p "$INSTALL_DIR"
    # Copy source if running from repo
    if [ -d "$REPO_DIR/backend" ]; then
        cp -r "$REPO_DIR/backend" "$INSTALL_DIR/"
        cp -r "$REPO_DIR/src" "$INSTALL_DIR/" 2>/dev/null || true
    fi
fi

python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --quiet --upgrade pip
"$VENV_DIR/bin/pip" install --quiet \
    "pymodbus>=3.6.0" \
    "fastapi>=0.104.0" \
    "uvicorn[standard]>=0.24.0" \
    "pydantic-settings>=2.0.0"

echo "Python venv ready at $VENV_DIR"

# --- 6. Systemd service ---
echo "[6/6] Installing systemd service..."
sudo cp "$SCRIPT_DIR/pi-factory.service" /etc/systemd/system/pi-factory.service
# Update WorkingDirectory and ExecStart if install dir differs
if [ "$INSTALL_DIR" != "/home/pi/factorylm/services/plc-modbus" ]; then
    sudo sed -i "s|/home/pi/factorylm/services/plc-modbus|$INSTALL_DIR|g" \
        /etc/systemd/system/pi-factory.service
fi
sudo systemctl daemon-reload
sudo systemctl enable pi-factory.service
sudo systemctl start pi-factory.service

echo ""
echo "=== Pi Factory Ready ==="
echo "  Dashboard:  http://pi-factory.local:8000"
echo "  API:        http://pi-factory.local:8000/api/devices"
echo "  SSE stream: http://pi-factory.local:8000/api/stream"
echo "  Logs:       journalctl -u pi-factory -f"
echo ""
echo "Plug any PLC into this switch. It will appear automatically."
