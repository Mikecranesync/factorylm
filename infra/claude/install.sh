#!/bin/bash
# Install the cluster-wide Claude hardening (hooks, skills, global rules) on this node.
# Idempotent — safe to re-run after every `git -C ~/factorylm pull`.
#
# What it does:
#   1. Copies hooks into ~/.claude/hooks/ and skills into ~/.claude/skills/
#   2. Merges the three hook registrations into ~/.claude/settings.json
#      (only if a hook entry with the same command isn't already present)
#   3. Ensures ~/.claude/CLAUDE.md imports infra/claude/CLAUDE-GLOBAL-RULES.md
#
# Provenance: docs/insights/README.md
set -euo pipefail

SRC="$(cd "$(dirname "$0")" && pwd)"
case "$SRC" in
  */worktrees/*)
    echo "ERROR: running from a temporary worktree ($SRC)." >&2
    echo "The CLAUDE.md import would dangle when the worktree is removed." >&2
    echo "Run from the main checkout instead: bash ~/factorylm/infra/claude/install.sh" >&2
    exit 1 ;;
esac
CLAUDE_DIR="$HOME/.claude"
mkdir -p "$CLAUDE_DIR/hooks" "$CLAUDE_DIR/skills/resume"

# 1. Hooks + skills
cp "$SRC/hooks/"*.sh "$CLAUDE_DIR/hooks/"
chmod +x "$CLAUDE_DIR/hooks/"*.sh
cp "$SRC/skills/resume/SKILL.md" "$CLAUDE_DIR/skills/resume/SKILL.md"
cp "$SRC/skills/ship.md" "$CLAUDE_DIR/skills/ship.md"
echo "installed: hooks (reap-orphaned-lsp, shared-file-guard, ruff-on-edit), skills (/resume, /ship)"

# 2. settings.json hook registration (python3 stdlib; system 3.9 is fine)
SETTINGS="$CLAUDE_DIR/settings.json" python3 - <<'PYEOF'
import json, os

path = os.environ["SETTINGS"]
home = os.path.expanduser("~")
try:
    with open(path) as f:
        settings = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    settings = {}

hooks = settings.setdefault("hooks", {})

def has_command(event, needle):
    for group in hooks.get(event, []):
        for h in group.get("hooks", []):
            if needle in h.get("command", ""):
                return True
    return False

def add(event, matcher, command, timeout):
    if has_command(event, os.path.basename(command.split()[-1])):
        return False
    group = {"hooks": [{"type": "command", "command": command, "timeout": timeout}]}
    if matcher:
        group["matcher"] = matcher
    hooks.setdefault(event, []).append(group)
    return True

changed = False
changed |= add("SessionStart", None,
               "bash %s/.claude/hooks/reap-orphaned-lsp.sh" % home, 15)
changed |= add("PreToolUse", "Edit|Write",
               "bash %s/.claude/hooks/shared-file-guard.sh" % home, 10)
changed |= add("PostToolUse", "Edit|Write",
               "bash %s/.claude/hooks/ruff-on-edit.sh" % home, 30)

if changed:
    with open(path, "w") as f:
        json.dump(settings, f, indent=2)
        f.write("\n")
    print("settings.json: hook registrations added")
else:
    print("settings.json: hooks already registered")
PYEOF

# 3. Global rules import in ~/.claude/CLAUDE.md
RULES="$SRC/CLAUDE-GLOBAL-RULES.md"
CLAUDE_MD="$CLAUDE_DIR/CLAUDE.md"
touch "$CLAUDE_MD"
if grep -qF "CLAUDE-GLOBAL-RULES.md" "$CLAUDE_MD"; then
  echo "CLAUDE.md: global rules import already present"
else
  printf '\n## Cluster-wide Claude Rules (insights-derived)\n\n@%s\n' "$RULES" >> "$CLAUDE_MD"
  echo "CLAUDE.md: added import of $RULES"
fi

echo "done. New sessions pick everything up automatically; running sessions need /hooks or a restart."
