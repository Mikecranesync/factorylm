#!/bin/bash
# PostToolUse hook: auto-format and lint Python files after Edit/Write.
#
# Payload source: stdin JSON. $CLAUDE_TOOL_INPUT is NOT set by the harness
# (verified 2026-08-09 by dumping the hook environment: CLAUDE_PROJECT_DIR /
# CLAUDE_CODE_SESSION_ID / CLAUDE_PID are set; CLAUDE_TOOL_INPUT is empty and
# CLAUDE_FILE_PATH is absent entirely). This hook read only that env var, so it
# had never run in any project. Its jq path was wrong too — the payload nests the
# path under .tool_input / .tool_response, not at the top level — so it would
# still have missed even with the variable populated.
JQ=/opt/homebrew/bin/jq
[ -x "$JQ" ] || JQ=jq

FILE=$(cat | "$JQ" -r '.tool_response.filePath // .tool_input.file_path // empty' 2>/dev/null)

if [[ "$FILE" == *.py ]] && [[ -f "$FILE" ]]; then
  /opt/homebrew/bin/ruff check --fix "$FILE" >/dev/null 2>&1 || true
  /opt/homebrew/bin/ruff format "$FILE" >/dev/null 2>&1 || true
  # Surface anything ruff could NOT auto-fix back to the model now,
  # instead of letting it be discovered as a red CI check later.
  REMAINING=$(/opt/homebrew/bin/ruff check --output-format=concise "$FILE" 2>/dev/null | head -20)
  if [ -n "$REMAINING" ]; then
    "$JQ" -n --arg r "$REMAINING" '{
      hookSpecificOutput: {
        hookEventName: "PostToolUse",
        additionalContext: ("ruff auto-fix left unresolved lint errors in this file — fix them before moving on:\n" + $r)
      }
    }'
  fi
fi
exit 0
