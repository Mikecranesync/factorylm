#!/usr/bin/env python3
"""Merge cluster-canonical Claude Code permission entries into ~/.claude/settings.json.

Called by the factorylm Ansible playbook. Idempotent: safe to re-run.

- Preserves all existing keys (statusLine, effortLevel, hooks, etc.).
- Adds any canonical entries missing from permissions.allow.
- Leaves user-added local entries untouched.
- Writes a version marker to ~/.claude/.permissions-merged-v<N> so Ansible's
  `creates:` idempotency skips re-runs at the same version.

Bump CANONICAL_VERSION whenever CANONICAL_ALLOW changes so the task re-fires.
"""
from __future__ import annotations

import json
import pathlib
import sys

CANONICAL_VERSION = 1

CANONICAL_ALLOW = [
    "Bash(ssh *)",
    "Bash(scp *)",
    "Bash(rsync *)",
    "Bash(tailscale *)",
    "Bash(/opt/homebrew/bin/tailscale *)",
    "Bash(nc -z *)",
    "Bash(ping -c* *)",
    "Bash(dig *)",
    "Bash(host *)",
]


def main() -> int:
    claude_dir = pathlib.Path.home() / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    settings_path = claude_dir / "settings.json"
    marker = claude_dir / f".permissions-merged-v{CANONICAL_VERSION}"

    if marker.exists():
        print(f"marker {marker.name} present — nothing to do")
        return 0

    if settings_path.exists():
        try:
            data = json.loads(settings_path.read_text())
        except json.JSONDecodeError as exc:
            print(f"ERROR: {settings_path} is not valid JSON: {exc}", file=sys.stderr)
            return 2
    else:
        data = {}

    perms = data.setdefault("permissions", {})
    allow = perms.setdefault("allow", [])
    if not isinstance(allow, list):
        print(f"ERROR: permissions.allow is not a list: {type(allow).__name__}", file=sys.stderr)
        return 2

    added = 0
    for entry in CANONICAL_ALLOW:
        if entry not in allow:
            allow.append(entry)
            added += 1

    perms.setdefault("deny", [])
    perms.setdefault("defaultMode", "auto")

    settings_path.write_text(json.dumps(data, indent=2) + "\n")
    marker.touch()

    print(f"merged: {added} new of {len(CANONICAL_ALLOW)} canonical entries (v{CANONICAL_VERSION})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
