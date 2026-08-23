#!/bin/bash
# SessionStart hook: reap orphaned pyright / language-server workers.
#
# Motivation: orphaned pyright workers (and once a wedged ctkd daemon) caused
# CPU thrashing that three separate sessions burned time re-diagnosing.
# This makes the cleanup automatic instead of a rediscovery each time.
#
# Safety rules — a process is only killed if ALL hold:
#   1. Its command line matches a known language-server worker pattern
#      (pyright/langserver). ctkd is system-owned, so it is only REPORTED,
#      never killed (no passwordless sudo on this box anyway).
#   2. It is orphaned: parent PID is 1 (launchd adopted it).
#   3. It is older than 30 minutes.
#   4. It is not attached to a terminal (TTY column is "??").
# Everything killed (or flagged) is logged to ~/.claude/reaped.log.

LOG="$HOME/.claude/reaped.log"
NOW=$(date +%s)

# etime is [[dd-]hh:]mm:ss — convert to seconds
etime_to_secs() {
  local e="$1" d=0 h=0 m=0 s=0 rest
  if [[ "$e" == *-* ]]; then d=${e%%-*}; e=${e#*-}; fi
  IFS=: read -r a b c <<< "$e"
  if [[ -n "$c" ]]; then h=$a; m=$b; s=$c
  elif [[ -n "$b" ]]; then m=$a; s=$b
  else s=$a; fi
  echo $(( 10#$d*86400 + 10#$h*3600 + 10#$m*60 + 10#$s ))
}

ps -axo pid=,ppid=,etime=,tty=,command= | grep -Ei 'pyright|langserver' | grep -v grep | \
while read -r pid ppid etime tty cmd; do
  [ "$ppid" = "1" ] || continue
  [ "$tty" = "??" ] || continue
  age=$(etime_to_secs "$etime")
  [ "$age" -gt 1800 ] || continue
  if kill "$pid" 2>/dev/null; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') killed pid=$pid age=${age}s cmd=${cmd:0:120}" >> "$LOG"
  fi
done

# ctkd: report-only (system daemon; killing needs sudo and may be wrong fix)
CTKD_CPU=$(ps -axo pcpu=,command= | awk '/[c]tkd/ {print int($1); exit}')
if [ -n "$CTKD_CPU" ] && [ "$CTKD_CPU" -gt 50 ]; then
  echo "$(date '+%Y-%m-%d %H:%M:%S') WARNING ctkd at ${CTKD_CPU}% CPU — wedged? (not killed, needs sudo)" >> "$LOG"
  echo "{\"systemMessage\": \"ctkd daemon is at ${CTKD_CPU}% CPU — likely wedged, see ~/.claude/reaped.log\"}"
fi
exit 0
