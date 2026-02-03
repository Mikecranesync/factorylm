#!/bin/bash
# FactoryLM Edge Device - One-Command Setup
# Run: curl -sSL <url>/install.sh | bash
# Or:  bash install.sh

set -e

echo "========================================"
echo "FactoryLM Edge Device Setup"
echo "========================================"

# Check if running on Raspberry Pi
if [ -f /proc/cpuinfo ] && grep -q "Raspberry Pi\|BCM" /proc/cpuinfo 2>/dev/null; then
    echo "Detected: Raspberry Pi"
    IS_PI=true
else
    echo "Warning: This doesn't appear to be a Raspberry Pi"
    echo "GPIO functionality will be simulated"
    IS_PI=false
fi

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
echo "Python version: $PYTHON_VERSION"

# Update system
echo ""
echo "Step 1: Updating system packages..."
sudo apt-get update -qq
sudo apt-get install -y -qq python3 python3-pip python3-venv git

# Determine install directory
if [ -n "$1" ]; then
    INSTALL_DIR="$1"
else
    INSTALL_DIR="$HOME/factorylm-edge"
fi
echo ""
echo "Step 2: Installing to $INSTALL_DIR..."

if [ -d "$INSTALL_DIR" ]; then
    echo "Directory exists, updating..."
    cd "$INSTALL_DIR"
else
    mkdir -p "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

# Copy current files if running from source
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/edge_server.py" ]; then
    echo "Copying source files..."
    cp "$SCRIPT_DIR"/*.py "$INSTALL_DIR/" 2>/dev/null || true
    cp "$SCRIPT_DIR"/*.txt "$INSTALL_DIR/" 2>/dev/null || true
    cp "$SCRIPT_DIR"/*.json "$INSTALL_DIR/" 2>/dev/null || true
fi

# Create virtual environment
echo ""
echo "Step 3: Creating Python virtual environment..."
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
echo ""
echo "Step 4: Installing Python dependencies..."
pip install --upgrade pip -q

if [ "$IS_PI" = true ]; then
    pip install pymodbus>=3.6.0 RPi.GPIO fastapi uvicorn pydantic pydantic-settings -q
else
    pip install pymodbus>=3.6.0 fastapi uvicorn pydantic pydantic-settings -q
fi

# Create default config if not exists
if [ ! -f config.json ]; then
    echo ""
    echo "Step 5: Creating default configuration..."
    cat > config.json << 'EOF'
{
    "name": "Factory I/O Default",
    "description": "Basic simulation with buttons and LEDs",
    "server": {
        "host": "0.0.0.0",
        "port": 502
    },
    "inputs": [
        {"coil": 0, "gpio": 17, "name": "Start_Button"},
        {"coil": 1, "gpio": 27, "name": "Stop_Button"},
        {"coil": 2, "gpio": 22, "name": "E_Stop"}
    ],
    "outputs": [
        {"coil": 10, "gpio": 5, "name": "LED_Green"},
        {"coil": 11, "gpio": 6, "name": "LED_Red"},
        {"coil": 12, "gpio": 13, "name": "Relay1"},
        {"coil": 13, "gpio": 19, "name": "Relay2"}
    ]
}
EOF
fi

# Create systemd service
echo ""
echo "Step 6: Creating systemd service..."
sudo tee /etc/systemd/system/factorylm-edge.service > /dev/null << EOF
[Unit]
Description=FactoryLM Edge Modbus Server
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/.venv/bin/python edge_server.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload

echo ""
echo "========================================"
echo "Installation Complete!"
echo "========================================"
echo ""
echo "To start manually:"
echo "  cd $INSTALL_DIR"
echo "  source .venv/bin/activate"
echo "  sudo python edge_server.py"
echo ""
echo "To test without sudo (port 5020):"
echo "  python edge_server.py --port 5020"
echo ""
echo "To enable auto-start on boot:"
echo "  sudo systemctl enable factorylm-edge"
echo "  sudo systemctl start factorylm-edge"
echo ""
echo "To check status:"
echo "  sudo systemctl status factorylm-edge"
echo ""
echo "Configuration file: $INSTALL_DIR/config.json"
echo ""
echo "Test connection from another machine:"
echo "  from pymodbus.client import ModbusTcpClient"
echo "  client = ModbusTcpClient('<PI_IP>', port=502)"
echo "  client.connect()"
echo "  client.read_coils(0, 20)"
echo ""
