#!/bin/bash
# health-check.sh — CHARLIE node health monitor.
#
# Run by launchd every 300 s (com.factorylm.health-monitor; tracked plist in
# infra/launchd/charlie/). Deterministic checks only, no LLM (Cluster Law 2):
#   1. required local services answer on their ports
#   2. no com.factorylm.* / com.mira.* LaunchAgent is crash-looping or dead
#   3. the Data volume is under the disk threshold
# One status line per run to $LOG. A line to $ALERTS (plus an optional webhook)
# only when the failure set CHANGES, so a persistent fault alerts once, not
# every five minutes. Always exits 0: the log is the signal, and a non-zero
# exit would make this agent flag itself in check 2.
#
# Why this exists: factorylm#221. The LaunchAgent pointed at a script that was
# never committed, so it exited 127 on every fire for months while brain-mcp
# respawned ~37k times unnoticed (#220, #223). Check 2 is what catches that:
# a job whose `runs` counter climbs between two checks is looping, whatever
# its exit code says.
#
# Targets macOS /bin/bash 3.2 — no associative arrays, no mapfile.
set -u

STATE_DIR="${FLM_HEALTH_STATE_DIR:-$HOME/.factorylm/health}"
LOG="${FLM_HEALTH_LOG:-/tmp/factorylm-health.log}"
ALERTS="${FLM_HEALTH_ALERTS:-/tmp/factorylm-health.alerts}"
WEBHOOK_FILE="$STATE_DIR/webhook_url"          # optional: one webhook URL, mode 600, never in git
MAX_LOG_BYTES=1048576
DISK_WARN_PCT="${FLM_HEALTH_DISK_PCT:-90}"
LOOP_SPAWNS="${FLM_HEALTH_LOOP_SPAWNS:-5}"      # more spawns than this between runs = crash loop
SELF_LABEL="com.factorylm.health-monitor"

# name|kind|target    http: GET must return 2xx/3xx    tcp: port must accept a connect
SERVICES="
brain-ingest|http|http://127.0.0.1:8500/health
brain-mcp|tcp|8501
cao-server|http|http://127.0.0.1:9889/health
qdrant|tcp|8000
"

mkdir -p "$STATE_DIR"
now() { date '+%Y-%m-%dT%H:%M:%S%z'; }
rotate() {
  if [ -f "$1" ] && [ "$(stat -f%z "$1")" -gt "$MAX_LOG_BYTES" ]; then
    tail -c 262144 "$1" > "$1.tmp" && mv "$1.tmp" "$1"
  fi
}
rotate "$LOG"
rotate "$ALERTS"

fails=()

# --- 1. services -------------------------------------------------------------
while IFS='|' read -r name kind target; do
  [ -z "$name" ] && continue
  case "$kind" in
    http) curl -sf -m 5 -o /dev/null "$target" || fails+=("$name: no 2xx from $target") ;;
    tcp)  nc -z -w 2 127.0.0.1 "$target" >/dev/null 2>&1 || fails+=("$name: nothing listening on :$target") ;;
  esac
done <<SVC
$SERVICES
SVC

# --- 2. LaunchAgents ---------------------------------------------------------
uid=$(id -u)
agents=$(launchctl list 2>/dev/null | awk 'NR>1 && $3 ~ /^com\.(factorylm|mira)\./ {print $3}')
n_agents=0
for label in $agents; do
  [ "$label" = "$SELF_LABEL" ] && continue
  n_agents=$((n_agents + 1))
  info=$(launchctl print "gui/$uid/$label" 2>/dev/null)
  runs=$(printf '%s\n' "$info" | awk -F'= ' '/^[[:space:]]*runs = /{print $2; exit}')
  exitcode=$(printf '%s\n' "$info" | awk -F'= ' '/^[[:space:]]*last exit code = /{print $2; exit}')
  state=$(printf '%s\n' "$info" | awk -F'= ' '/^[[:space:]]*state = /{print $2; exit}')
  runs=${runs:-0}
  sf="$STATE_DIR/runs.$label"
  prev=$(cat "$sf" 2>/dev/null || echo "$runs")
  printf '%s\n' "$runs" > "$sf"
  delta=$((runs - prev))
  if [ "$delta" -gt "$LOOP_SPAWNS" ]; then
    fails+=("$label: crash-looping ($delta spawns since last check, last exit ${exitcode:-?})")
  elif [ "$state" != "running" ] && [ -n "$exitcode" ] \
       && [ "$exitcode" != "0" ] && [ "$exitcode" != "(never exited)" ]; then
    fails+=("$label: not running, last exit $exitcode")
  fi
done

# --- 3. disk -----------------------------------------------------------------
vol="/System/Volumes/Data"
[ -d "$vol" ] || vol="/"
pct=$(df -P "$vol" | awk 'NR==2 {gsub("%", "", $5); print $5}')
[ "${pct:-0}" -ge "$DISK_WARN_PCT" ] && fails+=("disk: $vol at ${pct}% (threshold ${DISK_WARN_PCT}%)")

# --- report ------------------------------------------------------------------
if [ "${#fails[@]}" -eq 0 ]; then
  status=OK; detail=""
else
  status=FAIL; detail=$(printf ' | %s' "${fails[@]}")
fi
echo "$(now) $status disk=${pct:-?}% agents=$n_agents fails=${#fails[@]}$detail" >> "$LOG"

# alert only when the failure set changes (fires once per fault, once per recovery)
sig=$(printf '%s\n' ${fails[@]+"${fails[@]}"} | sort)
prev_sig=$(cat "$STATE_DIR/last_fails" 2>/dev/null || true)
if [ "$sig" != "$prev_sig" ]; then
  printf '%s\n' "$sig" > "$STATE_DIR/last_fails"
  host=$(hostname -s)
  if [ "$status" = OK ]; then
    msg="[$host] health recovered: all checks passing"
  else
    msg="[$host] health $status$detail"
  fi
  echo "$(now) $msg" >> "$ALERTS"
  if [ -s "$WEBHOOK_FILE" ]; then
    payload=$(printf '{"content": "%s"}' "$(printf '%s' "$msg" | sed 's/["\\]/\\&/g')")
    curl -sf -m 10 -H 'Content-Type: application/json' --data "$payload" "$(cat "$WEBHOOK_FILE")" \
      >/dev/null 2>&1 || echo "$(now) webhook post failed" >> "$ALERTS"
  fi
fi
exit 0
