#!/usr/bin/env bash
# FactoryLM Cluster Bootstrap
# Run on any machine to join the cluster brain.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/Mikecranesync/factorylm/main/bootstrap.sh | bash
#   — or —
#   git clone https://github.com/Mikecranesync/factorylm.git ~/factorylm && ~/factorylm/bootstrap.sh

set -euo pipefail

REPO_URL="https://github.com/Mikecranesync/factorylm.git"
REPO_DIR="$HOME/factorylm"
CLAUDE_DIR="$HOME/.claude"

# --- Detect node identity by IP ---
detect_node() {
  local ips
  ips=$(ifconfig 2>/dev/null | grep 'inet ' | awk '{print $2}' || ip -4 addr show 2>/dev/null | grep -oP '(?<=inet\s)\d+(\.\d+){3}' || true)

  if echo "$ips" | grep -q "192.168.1.10"; then echo "ALPHA";  return; fi
  if echo "$ips" | grep -q "192.168.1.11"; then echo "BRAVO";  return; fi
  if echo "$ips" | grep -q "192.168.1.12"; then echo "CHARLIE"; return; fi
  if echo "$ips" | grep -q "192.168.1.20"; then echo "PLC";    return; fi
  if echo "$ips" | grep -q "192.168.1.30"; then echo "PI";     return; fi

  # Check for Tailscale — if connected but no LAN match, it's TRAVEL
  if command -v tailscale &>/dev/null && tailscale status &>/dev/null; then
    echo "TRAVEL"; return
  fi

  echo "UNKNOWN"
}

NODE=$(detect_node)

echo "=== FactoryLM Cluster Bootstrap ==="
echo "Detected node: $NODE"
echo ""

# --- 1. Clone or pull the repo ---
if [ -d "$REPO_DIR/.git" ]; then
  echo "[1/4] Pulling latest from origin..."
  git -C "$REPO_DIR" pull --ff-only origin main
else
  echo "[1/4] Cloning factorylm repo..."
  git clone "$REPO_URL" "$REPO_DIR"
fi

# --- 2. Create ~/.claude/ if needed ---
mkdir -p "$CLAUDE_DIR"

# --- 3. Write ~/.claude/CLAUDE.md with @import ---
CLAUDE_MD="$CLAUDE_DIR/CLAUDE.md"

# Preserve existing content if present (append import if missing)
if [ -f "$CLAUDE_MD" ] && grep -q "@$REPO_DIR/CLUSTER.md" "$CLAUDE_MD"; then
  echo "[2/4] ~/.claude/CLAUDE.md already imports CLUSTER.md — skipping."
else
  cat > "$CLAUDE_MD" <<HEREDOC
# FactoryLM Cluster Node: $NODE

You are running on the **$NODE** node of the FactoryLM cluster.
All cluster context, laws, and procedures are defined in:

@$REPO_DIR/CLUSTER.md

To update cluster context: \`git -C $REPO_DIR pull\`
HEREDOC
  echo "[2/4] Wrote ~/.claude/CLAUDE.md (node=$NODE, imports CLUSTER.md)"
fi

# --- 4. Write node identity file ---
echo "$NODE" > "$REPO_DIR/.node-identity"
echo "[3/4] Wrote .node-identity = $NODE"

# --- 5. Verify ---
echo "[4/4] Verifying..."
if [ -f "$REPO_DIR/CLUSTER.md" ] && [ -f "$CLAUDE_MD" ]; then
  echo ""
  echo "=== Bootstrap complete ==="
  echo "  Node:        $NODE"
  echo "  Repo:        $REPO_DIR"
  echo "  CLAUDE.md:   $CLAUDE_MD"
  echo "  CLUSTER.md:  $REPO_DIR/CLUSTER.md"
  echo ""
  echo "Run 'claude' in any directory — this machine now has full cluster context."
else
  echo "ERROR: Bootstrap verification failed." >&2
  exit 1
fi
