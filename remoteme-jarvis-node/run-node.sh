#!/usr/bin/env bash
# Jarvis Node launcher — portable (macOS + Linux).
#
# Binds to the Tailscale IPv4 ONLY. The /shell, /files, /screenshot endpoints are
# unauthenticated, so the node must never be reachable off the tailnet. We never
# bind 0.0.0.0 (that would expose it on the LAN too). If Tailscale is down we fall
# back to 127.0.0.1 (local-only) rather than something world-reachable.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

# launchd/systemd start us with a minimal PATH. Add ~/.local/bin so the doppler
# CLI is found. We deliberately do NOT prepend Homebrew here — that would shadow
# /usr/bin/python3 (which holds the deps) with a bare Homebrew python.
export PATH="$HOME/.local/bin:$PATH"

PORT="${JARVIS_PORT:-8765}"

# Pick the Python that actually has the deps, regardless of PATH order.
PY=""
for c in /usr/bin/python3 python3 /opt/homebrew/bin/python3 /usr/local/bin/python3 python; do
  cc="$(command -v "$c" 2>/dev/null || true)"
  [ -z "$cc" ] && continue
  if "$cc" -c "import uvicorn, fastapi" 2>/dev/null; then PY="$cc"; break; fi
done
if [ -z "$PY" ]; then
  echo "ERROR: no python found with uvicorn+fastapi installed. Run install-node.sh." >&2
  exit 1
fi

# Resolve the Tailscale IPv4 (tailnet-only bind). Try explicit binary locations;
# Homebrew's tailscaled on this fleet uses a non-default socket.
TS_BIN=""
for c in /opt/homebrew/bin/tailscale /usr/local/bin/tailscale /usr/bin/tailscale; do
  [ -x "$c" ] && TS_BIN="$c" && break
done
[ -z "$TS_BIN" ] && TS_BIN="$(command -v tailscale 2>/dev/null || true)"
HOST=""
if [ -n "$TS_BIN" ]; then
  HOST="$("$TS_BIN" ip -4 2>/dev/null | head -1 || true)"
  if [ -z "$HOST" ] && [ -S /var/run/tailscale/tailscaled.sock ]; then
    HOST="$("$TS_BIN" --socket=/var/run/tailscale/tailscaled.sock ip -4 2>/dev/null | head -1 || true)"
  fi
fi
if [ -z "${HOST:-}" ]; then
  echo "WARN: Tailscale IP not found; binding 127.0.0.1 (node will be local-only)" >&2
  HOST="127.0.0.1"
fi

PY="$(command -v python3 || command -v python)"

# Resolve the bearer token. Prefer an explicit env var (laptops/Pi without Doppler);
# otherwise pull the single secret from Doppler factorylm/prd. Fail-closed: a node
# with no token refuses to start rather than serving /shell wide open.
TOKEN="${JARVIS_TOKEN:-}"
if [ -z "$TOKEN" ] && command -v doppler >/dev/null 2>&1; then
  TOKEN="$(doppler secrets get JARVIS_TOKEN -p factorylm -c prd --plain 2>/dev/null || true)"
fi
if [ -z "$TOKEN" ]; then
  echo "ERROR: JARVIS_TOKEN unset and not retrievable from Doppler — refusing to start (fail-closed)." >&2
  echo "       Set JARVIS_TOKEN in the env, or run 'doppler login' so the secret can be read." >&2
  exit 1
fi
export JARVIS_TOKEN="$TOKEN"

exec "$PY" -m uvicorn jarvis_node:app --host "$HOST" --port "$PORT"
