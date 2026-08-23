#!/bin/bash
# PreToolUse hook (Edit|Write): guard direct edits to shared conflict-magnet
# files — VERSION and CHANGELOG.md at a git repo root.
#
# Motivation: VERSION/CHANGELOG merge conflicts recurred across 4+ sessions;
# the durable fix is per-run dated fragment files assembled by a release job.
# This hook surfaces the policy ONCE as a permission prompt ("ask") instead of
# hard-denying, so a legitimately-authorized edit is one approval away and
# nothing loops around the gate.
#
# Bypass for repos where direct edits are fine: CLAUDE_ALLOW_SHARED_FILE_EDITS=1

[ "$CLAUDE_ALLOW_SHARED_FILE_EDITS" = "1" ] && exit 0

JQ=/opt/homebrew/bin/jq
[ -x "$JQ" ] || JQ=jq

FILE=$("$JQ" -r '.tool_input.file_path // empty' 2>/dev/null)
[ -n "$FILE" ] || exit 0

base=$(basename "$FILE")
case "$base" in
  VERSION|CHANGELOG.md|hot.md) ;;
  *) exit 0 ;;
esac

# Only guard files at a git repo root (VERSION elsewhere is fair game)
dir=$(dirname "$FILE")
if git -C "$dir" rev-parse --show-toplevel >/dev/null 2>&1; then
  top=$(git -C "$dir" rev-parse --show-toplevel)
  if [ "$dir" = "$top" ] || [[ "$FILE" == */wiki/hot.md ]]; then
    "$JQ" -n --arg f "$base" '{
      hookSpecificOutput: {
        hookEventName: "PreToolUse",
        permissionDecision: "ask",
        permissionDecisionReason: ("Shared-file conflict policy: " + $f + " is a known merge-conflict magnet. Prefer a per-run dated fragment file assembled by the release job. Approve only if a direct edit is genuinely intended.")
      }
    }'
    exit 0
  fi
fi
exit 0
