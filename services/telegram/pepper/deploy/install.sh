#!/bin/bash
#
# PEPPER Deploy System Installation Script
#
# Usage: ./install.sh
#

set -e

echo "========================================"
echo "PEPPER Deploy System Installer"
echo "========================================"
echo

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Error: This script must be run as root"
    exit 1
fi

# Configuration
PEPPER_HOME="/root/.pepper"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLI_SOURCE="${SCRIPT_DIR}/cli.py"
CLI_DEST="/usr/local/bin/pepper"

echo "1. Creating PEPPER home directory..."
mkdir -p "${PEPPER_HOME}"/{versions,state,rollback}
echo "   ✓ Created ${PEPPER_HOME}"

echo "2. Installing pepper CLI..."
if [ -f "${CLI_DEST}" ]; then
    echo "   Warning: ${CLI_DEST} already exists"
    read -p "   Overwrite? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "   Skipping CLI installation"
    else
        cp "${CLI_SOURCE}" "${CLI_DEST}"
        chmod +x "${CLI_DEST}"
        echo "   ✓ Installed ${CLI_DEST}"
    fi
else
    cp "${CLI_SOURCE}" "${CLI_DEST}"
    chmod +x "${CLI_DEST}"
    echo "   ✓ Installed ${CLI_DEST}"
fi

echo "3. Verifying installation..."
if command -v pepper &> /dev/null; then
    echo "   ✓ pepper command available"
else
    echo "   ✗ pepper command not found in PATH"
    exit 1
fi

echo "4. Creating initial state files..."
cat > "${PEPPER_HOME}/state/sessions.json" << 'EOF'
{
  "active_sessions": {},
  "session_count": 0
}
EOF

cat > "${PEPPER_HOME}/state/routing.json" << 'EOF'
{
  "routing_table": {},
  "twin_mappings": {},
  "active_routes": 0
}
EOF

cat > "${PEPPER_HOME}/state/runtime_config.json" << 'EOF'
{
  "runtime_config": {}
}
EOF

cat > "${PEPPER_HOME}/state/metrics.json" << 'EOF'
{
  "message_count": 0,
  "error_count": 0,
  "uptime_seconds": 0
}
EOF

echo "   ✓ Created initial state files"

echo
echo "========================================"
echo "Installation Complete!"
echo "========================================"
echo
echo "PEPPER Deploy System is now installed."
echo
echo "Quick Start:"
echo "  pepper status           # Check deployment status"
echo "  pepper deploy           # Deploy new version"
echo "  pepper rollback         # Rollback to previous"
echo
echo "Documentation:"
echo "  cat ${SCRIPT_DIR}/README.md"
echo
echo "Next Steps:"
echo "  1. Configure paths in /usr/local/bin/pepper if needed"
echo "  2. Initialize your first deployment: pepper deploy"
echo
