#!/bin/bash
set -e

# ============================================
# FactoryLM Raspberry Pi Zero-Touch Setup
# ============================================
# Copy this file to /boot/firstrun.sh on your SD card
# Then add to cmdline.txt:
#   systemd.run=/boot/firstrun.sh systemd.run_success_action=none
# ============================================

# ================== CONFIGURATION ==================
# IMPORTANT: Replace this with your actual Tailscale auth key
# Get one at: https://login.tailscale.com/admin/settings/keys
# Settings: Reusable=YES, Ephemeral=NO, Pre-approved=YES
TAILSCALE_AUTHKEY="tskey-auth-REPLACE_ME"

# Static IP for direct ethernet connection (no router needed)
STATIC_ETH0_IP="192.168.5.2"

# Hostname prefix (will append machine ID for uniqueness)
HOSTNAME_PREFIX="factory-pi"
# ===================================================

LOG="/var/log/firstrun.log"
exec > >(tee -a "$LOG") 2>&1

echo "=============================================="
echo "FactoryLM Raspberry Pi Setup"
echo "Started: $(date)"
echo "=============================================="

# Validate auth key was replaced
if [[ "$TAILSCALE_AUTHKEY" == "tskey-auth-REPLACE_ME" ]]; then
    echo "ERROR: You must replace TAILSCALE_AUTHKEY with your actual key!"
    echo "Get one at: https://login.tailscale.com/admin/settings/keys"
    exit 1
fi

# Generate unique hostname from machine ID
UNIQUE_ID=$(cat /etc/machine-id | cut -c1-8)
FULL_HOSTNAME="${HOSTNAME_PREFIX}-${UNIQUE_ID}"
echo "Hostname: $FULL_HOSTNAME"

# Step 1: Wait for network connectivity
echo ""
echo "[1/6] Waiting for network..."
for i in {1..60}; do
    if ping -c 1 -W 2 google.com &>/dev/null; then
        echo "      Network available after ${i} seconds"
        break
    fi
    if [ $i -eq 60 ]; then
        echo "      WARNING: Network not available after 60s, continuing anyway..."
    fi
    sleep 1
done

# Step 2: Update package lists
echo ""
echo "[2/6] Updating package lists..."
apt-get update -qq

# Step 3: Install Tailscale
echo ""
echo "[3/6] Installing Tailscale..."
if ! command -v tailscale &>/dev/null; then
    curl -fsSL https://tailscale.com/install.sh | sh
else
    echo "      Tailscale already installed"
fi

# Step 4: Authenticate Tailscale
echo ""
echo "[4/6] Authenticating Tailscale..."
tailscale up \
    --authkey="$TAILSCALE_AUTHKEY" \
    --accept-routes \
    --ssh \
    --hostname="$FULL_HOSTNAME"

# Get assigned Tailscale IP
sleep 2
TAILSCALE_IP=$(tailscale ip -4 2>/dev/null || echo "pending")
echo "      Tailscale IP: $TAILSCALE_IP"

# Step 5: Configure static IP on eth0 for direct laptop connection
echo ""
echo "[5/6] Configuring static IP on eth0..."
if ! grep -q "interface eth0" /etc/dhcpcd.conf; then
    cat >> /etc/dhcpcd.conf << EOF

# FactoryLM: Static IP for direct laptop connection
# Connect laptop to Pi via ethernet, set laptop to 192.168.5.1
interface eth0
static ip_address=${STATIC_ETH0_IP}/24
static routers=192.168.5.1
static domain_name_servers=8.8.8.8 8.8.4.4

EOF
    echo "      Static IP configured: $STATIC_ETH0_IP"
else
    echo "      Static IP already configured"
fi

# Step 6: Set hostname
echo ""
echo "[6/6] Setting hostname..."
hostnamectl set-hostname "$FULL_HOSTNAME"
echo "127.0.1.1 $FULL_HOSTNAME" >> /etc/hosts

# Mark setup as complete
touch /boot/firstrun_complete
touch /var/log/firstrun_complete

# Summary
echo ""
echo "=============================================="
echo "SETUP COMPLETE!"
echo "=============================================="
echo "Hostname:       $FULL_HOSTNAME"
echo "Tailscale IP:   $TAILSCALE_IP"
echo "Static eth0 IP: $STATIC_ETH0_IP"
echo "SSH access:"
echo "  - Via Tailscale: ssh pi@$FULL_HOSTNAME"
echo "  - Via Tailscale: ssh pi@$TAILSCALE_IP"
echo "  - Via ethernet:  ssh pi@$STATIC_ETH0_IP"
echo "Completed: $(date)"
echo "=============================================="

# Self-destruct - remove this script and cmdline modification
echo ""
echo "Cleaning up..."
rm -f /boot/firstrun.sh 2>/dev/null || true

# Remove the systemd.run from cmdline.txt if we can
if [ -f /boot/cmdline.txt ]; then
    sed -i 's/ systemd\.run=[^ ]*//g' /boot/cmdline.txt 2>/dev/null || true
    sed -i 's/ systemd\.run_success_action=[^ ]*//g' /boot/cmdline.txt 2>/dev/null || true
fi

echo "Rebooting in 5 seconds to apply network changes..."
sleep 5
reboot
