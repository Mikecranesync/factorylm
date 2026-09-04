#!/bin/bash
# deploy-charlie-runtime.sh — pin CHARLIE's LaunchAgents to a runtime checkout.
#
#   bash scripts/deploy-charlie-runtime.sh [ref]     # default: main
#
# The brain-ingest, brain-mcp and health-monitor agents run from
# ~/.factorylm/runtime/factorylm — a shallow, detached clone that ONLY this
# script moves. They used to run from the shared ~/factorylm checkout, which
# is whatever branch the last Claude/Codex session left it on; a half-resolved
# merge on one such branch put brain-mcp into a 37k-respawn loop (#220/#223).
# Nothing that runs unattended should depend on a developer's working tree.
#
# What it does: clone-or-fetch the ref, install brain deps into ~/brain-venv,
# copy the tracked plists from infra/launchd/charlie/, restart the agents,
# then verify each one from the outside. Exits non-zero if any check fails.
set -euo pipefail

REF="${1:-main}"
RUNTIME="$HOME/.factorylm/runtime/factorylm"
VENV="$HOME/brain-venv"
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ORIGIN="$(git -C "$REPO_DIR" remote get-url origin)"
AGENTS_DIR="$HOME/Library/LaunchAgents"
UID_="$(id -u)"
AGENTS="com.factorylm.brain-ingest com.factorylm.brain-mcp com.factorylm.health-monitor"

echo "[1/4] runtime checkout ($REF)"
if [ ! -d "$RUNTIME/.git" ]; then
  mkdir -p "$(dirname "$RUNTIME")"
  # sparse + blob-filtered: the agents import nothing outside services/, and the
  # full tree is ~650 MB of cookoff/simulation assets on a volume that is
  # chronically near full.
  git clone --quiet --depth 1 --single-branch --branch "$REF" --filter=blob:none --sparse "$ORIGIN" "$RUNTIME"
  git -C "$RUNTIME" sparse-checkout set services scripts infra
else
  git -C "$RUNTIME" fetch --quiet --depth 1 origin "$REF"
  git -C "$RUNTIME" checkout --quiet --detach FETCH_HEAD
fi
SHA="$(git -C "$RUNTIME" rev-parse --short HEAD)"
printf '%s %s %s\n' "$(date '+%Y-%m-%dT%H:%M:%S%z')" "$REF" "$SHA" >> "$(dirname "$RUNTIME")/DEPLOYED"
echo "      $RUNTIME @ $SHA"

echo "[2/4] brain deps into $VENV"
[ -x "$VENV/bin/pip" ] || python3 -m venv "$VENV"
"$VENV/bin/pip" install --quiet -r "$RUNTIME/services/brain/requirements.txt"

echo "[3/4] LaunchAgents"
for label in $AGENTS; do
  src="$RUNTIME/infra/launchd/charlie/$label.plist"
  [ -f "$src" ] || { echo "      missing $src" >&2; exit 1; }
  if cmp -s "$src" "$AGENTS_DIR/$label.plist" && launchctl print "gui/$UID_/$label" >/dev/null 2>&1; then
    # plist unchanged and loaded: kickstart alone restarts the process on the
    # new checkout, and avoids the bootout/bootstrap race entirely.
    :
  else
    cp "$src" "$AGENTS_DIR/$label.plist"
    launchctl bootout "gui/$UID_/$label" 2>/dev/null || true
    # bootout of a KeepAlive job is asynchronous and `launchctl print` stops
    # finding the label BEFORE teardown finishes, so polling print is not
    # enough: bootstrap in that window fails with "5: Input/output error".
    # Retry the bootstrap itself; on 2026-09-04 the window was a few seconds.
    ok=0
    for _ in $(seq 1 30); do
      if launchctl bootstrap "gui/$UID_" "$AGENTS_DIR/$label.plist" 2>/dev/null; then ok=1; break; fi
      sleep 1
    done
    [ "$ok" -eq 1 ] || { echo "      could not bootstrap $label after 30 s" >&2; exit 1; }
  fi
  launchctl kickstart -k "gui/$UID_/$label"
  echo "      restarted $label"
done
sleep 10

echo "[4/4] verify"
fail=0
check() { if "$@" >/dev/null 2>&1; then echo "      ok   $1 ${*:2}" | cut -c1-100; else echo "      FAIL $*" | cut -c1-100; fail=1; fi; }
check curl -sf -m 5 http://127.0.0.1:8500/health
check curl -sf -m 5 -X POST -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' \
  --data '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"deploy","version":"0"}}}' \
  http://127.0.0.1:8501/mcp
for label in com.factorylm.brain-ingest com.factorylm.brain-mcp; do
  wd="$(launchctl print "gui/$UID_/$label" | awk -F'= ' '/working directory =/{print $2; exit}')"
  if [ "$wd" = "$RUNTIME" ]; then echo "      ok   $label runs from runtime"; else echo "      FAIL $label runs from '$wd'"; fail=1; fi
done
hm="$(launchctl print "gui/$UID_/com.factorylm.health-monitor" | awk -F'= ' '/last exit code =/{print $2; exit}')"
if [ "$hm" = "0" ]; then echo "      ok   health-monitor exit 0"; else echo "      FAIL health-monitor last exit $hm"; fail=1; fi
if [ "$fail" -ne 0 ]; then
  echo "DEPLOY FAILED — see /tmp/brain-*/stderr.log, /tmp/factorylm-health.err" >&2
  exit 1
fi
echo "DEPLOYED $REF@$SHA"
