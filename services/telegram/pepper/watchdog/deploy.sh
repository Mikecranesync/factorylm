#!/bin/bash
# PEPPER Watchdog Deployment Script
# Installs and configures the watchdog monitoring system

set -e

echo "=========================================="
echo "PEPPER Watchdog Deployment"
echo "=========================================="

# Configuration
PEPPER_DIR="${PEPPER_DIR:-/root/pepper}"
WATCHDOG_DIR="$PEPPER_DIR/watchdog"
STATE_DIR="/root/.pepper-watchdog"
SERVICE_FILE="pepper-watchdog.service"
CONFIG_FILE="watchdog.yaml"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}Error: This script must be run as root${NC}"
   exit 1
fi

# Check Python version
echo -e "${YELLOW}Checking Python version...${NC}"
PYTHON_VERSION=$(python3 --version | awk '{print $2}')
if ! python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)"; then
    echo -e "${RED}Error: Python 3.9+ required (found $PYTHON_VERSION)${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Python $PYTHON_VERSION${NC}"

# Install dependencies
echo -e "${YELLOW}Installing dependencies...${NC}"
pip3 install -q -r "$WATCHDOG_DIR/requirements.txt"
echo -e "${GREEN}✓ Dependencies installed${NC}"

# Create state directory
echo -e "${YELLOW}Creating state directory...${NC}"
mkdir -p "$STATE_DIR"
mkdir -p "$STATE_DIR/baselines"
mkdir -p "$STATE_DIR/config_backups"
chmod 700 "$STATE_DIR"
echo -e "${GREEN}✓ State directory created: $STATE_DIR${NC}"

# Check if config exists
if [[ ! -f "$PEPPER_DIR/$CONFIG_FILE" ]]; then
    echo -e "${RED}Error: Config file not found: $PEPPER_DIR/$CONFIG_FILE${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Configuration found${NC}"

# Validate configuration
echo -e "${YELLOW}Validating configuration...${NC}"
if ! python3 -c "import yaml; yaml.safe_load(open('$PEPPER_DIR/$CONFIG_FILE'))"; then
    echo -e "${RED}Error: Invalid YAML in config file${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Configuration valid${NC}"

# Check required environment variables
echo -e "${YELLOW}Checking environment variables...${NC}"
if [[ -f "/root/.pepper/.env" ]]; then
    source /root/.pepper/.env
    echo -e "${GREEN}✓ Environment loaded${NC}"
else
    echo -e "${YELLOW}⚠ Warning: /root/.pepper/.env not found${NC}"
fi

REQUIRED_VARS=("PEPPER_PRIME_TOKEN" "GROQ_API_KEY")
for var in "${REQUIRED_VARS[@]}"; do
    if [[ -z "${!var}" ]]; then
        echo -e "${YELLOW}⚠ Warning: $var not set${NC}"
    else
        echo -e "${GREEN}✓ $var configured${NC}"
    fi
done

# Install systemd service
echo -e "${YELLOW}Installing systemd service...${NC}"

# Stop existing service if running
if systemctl is-active --quiet pepper-watchdog; then
    echo "Stopping existing watchdog service..."
    systemctl stop pepper-watchdog
fi

# Copy service file
cp "$WATCHDOG_DIR/$SERVICE_FILE" /etc/systemd/system/
chmod 644 /etc/systemd/system/$SERVICE_FILE

# Reload systemd
systemctl daemon-reload

echo -e "${GREEN}✓ Service installed${NC}"

# Enable service
echo -e "${YELLOW}Enabling service...${NC}"
systemctl enable pepper-watchdog
echo -e "${GREEN}✓ Service enabled${NC}"

# Start service
echo -e "${YELLOW}Starting watchdog...${NC}"
systemctl start pepper-watchdog

# Wait for startup
sleep 3

# Check status
if systemctl is-active --quiet pepper-watchdog; then
    echo -e "${GREEN}✓ Watchdog started successfully${NC}"
else
    echo -e "${RED}✗ Watchdog failed to start${NC}"
    systemctl status pepper-watchdog
    exit 1
fi

echo ""
echo "=========================================="
echo -e "${GREEN}Deployment Complete!${NC}"
echo "=========================================="
echo ""
echo "Service Status:"
systemctl status pepper-watchdog --no-pager | head -15
echo ""
echo "Commands:"
echo "  View logs:    journalctl -u pepper-watchdog -f"
echo "  Stop:         systemctl stop pepper-watchdog"
echo "  Restart:      systemctl restart pepper-watchdog"
echo "  Status:       systemctl status pepper-watchdog"
echo ""
echo "State Directory: $STATE_DIR"
echo "Configuration:   $PEPPER_DIR/$CONFIG_FILE"
echo ""
