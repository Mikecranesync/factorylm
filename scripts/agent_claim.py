#!/usr/bin/env python3
"""
agent_claim.py — Lease/claim management system to prevent duplicate work.

Leases live in .agents/leases/<item-slug>.json with structure:
  {agent_id, item, worktree, branch, started_at, heartbeat_at, status}

Subcommands:
  claim <item> [--agent-id X] [--worktree P] [--branch B] [--stale-hours N] [--no-preflight]
  heartbeat <item>
  release <item> [--status merged|abandoned]
  census [--reap]
"""

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Optional


def slugify(item: str) -> str:
    """Convert item name to a safe filename slug."""
    # Replace non-alphanumeric with hyphen
    slug = re.sub(r"[^a-z0-9]+", "-", item.lower()).strip("-")
    return slug


def get_lease_path(item: str, leases_dir: str = ".agents/leases") -> Path:
    """Get the lease file path for an item."""
    return Path(leases_dir) / f"{slugify(item)}.json"


def read_lease(item: str, leases_dir: str = ".agents/leases") -> Optional[Dict]:
    """Read lease file if it exists."""
    lease_path = get_lease_path(item, leases_dir)
    if not lease_path.exists():
        return None
    with open(lease_path, "r") as f:
        return json.load(f)


def write_lease(
    item: str, lease_data: Dict, leases_dir: str = ".agents/leases"
) -> None:
    """Write lease file (non-atomic)."""
    Path(leases_dir).mkdir(parents=True, exist_ok=True)
    lease_path = get_lease_path(item, leases_dir)
    with open(lease_path, "w") as f:
        json.dump(lease_data, f, indent=2)


def atomic_create_lease(
    item: str, lease_data: Dict, leases_dir: str = ".agents/leases"
) -> bool:
    """
    Atomically create a lease file using O_CREAT|O_EXCL.
    Returns True if created, False if file already exists.
    """
    Path(leases_dir).mkdir(parents=True, exist_ok=True)
    lease_path = get_lease_path(item, leases_dir)
    try:
        # O_CREAT|O_EXCL fails if file exists
        fd = os.open(str(lease_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        with os.fdopen(fd, "w") as f:
            json.dump(lease_data, f, indent=2)
        return True
    except FileExistsError:
        return False


def is_stale(heartbeat_at: str, stale_hours: int = 4) -> bool:
    """
    Check if a heartbeat timestamp is older than stale_hours.
    heartbeat_at should be UTC ISO-8601 string.
    """
    try:
        hb_time = datetime.fromisoformat(heartbeat_at.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        age = now - hb_time
        return age > timedelta(hours=stale_hours)
    except (ValueError, AttributeError):
        return True


def run_preflight_check(item: str, repo: Optional[str] = None) -> Optional[str]:
    """
    Check if work already appears merged.
    Run: gh pr list --state all --search <item>
         git log --all --grep=<item> --oneline
    Returns error message if work already done, None if clear.
    """
    try:
        # Check PRs
        cmd = ["gh", "pr", "list", "--state", "all", "--search", item]
        if repo:
            cmd.extend(["-R", repo])
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        if result.returncode == 0 and result.stdout.strip():
            # Found matching PRs
            return f"Work already has matching PR(s): {result.stdout.split()[0] if result.stdout else item}"

        # Check git log
        cmd = ["git", "log", "--all", "--grep", item, "--oneline"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        if result.returncode == 0 and result.stdout.strip():
            return f"Work already committed: {result.stdout.split()[0] if result.stdout else item}"
    except subprocess.TimeoutExpired:
        pass  # If gh/git timeout, allow claim (offline mode)
    except Exception:
        pass  # Preflight errors are non-fatal

    return None


def cmd_claim(
    item: str,
    agent_id: str = "claude",
    worktree: str = ".",
    branch: str = "main",
    stale_hours: int = 4,
    no_preflight: bool = False,
    repo: Optional[str] = None,
) -> int:
    """
    Claim an item. Exit 0 on success, 1 on fresh lease conflict, 2 on already-merged.
    """
    # Preflight check
    if not no_preflight:
        preflight_err = run_preflight_check(item, repo)
        if preflight_err:
            print(f"PREFLIGHT FAIL: {preflight_err}", file=sys.stderr)
            return 2

    # Check for existing lease
    existing = read_lease(item)
    if existing:
        hb = existing.get("heartbeat_at", "")
        if not is_stale(hb, stale_hours):
            print(
                f"CLAIM FAIL: fresh lease exists (heartbeat: {hb})",
                file=sys.stderr,
            )
            return 1
        else:
            # Lease is stale, remove it before claiming
            get_lease_path(item).unlink(missing_ok=True)

    # Try atomic create
    now = datetime.now(timezone.utc).isoformat()
    lease_data = {
        "agent_id": agent_id,
        "item": item,
        "worktree": worktree,
        "branch": branch,
        "started_at": now,
        "heartbeat_at": now,
        "status": "in_progress",
    }

    if atomic_create_lease(item, lease_data):
        print(json.dumps(lease_data, indent=2))
        return 0
    else:
        print("CLAIM FAIL: file exists (race condition)", file=sys.stderr)
        return 1


def cmd_heartbeat(item: str) -> int:
    """
    Update heartbeat timestamp. Exit 0 on success, 1 if lease doesn't exist.
    """
    existing = read_lease(item)
    if not existing:
        print(f"HEARTBEAT FAIL: no lease for {item}", file=sys.stderr)
        return 1

    existing["heartbeat_at"] = datetime.now(timezone.utc).isoformat()
    write_lease(item, existing)
    print(json.dumps(existing, indent=2))
    return 0


def cmd_release(item: str, status: str = "merged") -> int:
    """
    Release a lease. Exit 0 on success, 1 if lease doesn't exist.
    Appends one line to .agents/leases/HISTORY.log.
    """
    existing = read_lease(item)
    if not existing:
        print(f"RELEASE FAIL: no lease for {item}", file=sys.stderr)
        return 1

    # Remove lease file
    lease_path = get_lease_path(item)
    lease_path.unlink(missing_ok=True)

    # Append to history log
    Path(".agents/leases").mkdir(parents=True, exist_ok=True)
    history_path = Path(".agents/leases/HISTORY.log")
    timestamp = datetime.now(timezone.utc).isoformat()
    log_line = f"{timestamp} | {item} | status={status} | agent_id={existing.get('agent_id', 'unknown')}\n"
    with open(history_path, "a") as f:
        f.write(log_line)

    print(f"RELEASED: {item} ({status})")
    return 0


def cmd_census(reap: bool = False) -> int:
    """
    Show table of live vs stale leases.
    If --reap, delete stale leases.
    """
    leases_dir = Path(".agents/leases")
    if not leases_dir.exists():
        print("No leases found")
        return 0

    leases = [f for f in leases_dir.glob("*.json") if f.name != "HISTORY.log"]

    if not leases:
        print("No active leases")
        return 0

    live = []
    stale = []
    for lease_file in leases:
        with open(lease_file, "r") as f:
            lease_data = json.load(f)
        hb = lease_data.get("heartbeat_at", "")
        item_name = lease_file.stem
        if is_stale(hb, 4):
            stale.append((item_name, lease_file, lease_data))
        else:
            live.append((item_name, lease_file, lease_data))

    print(f"LIVE LEASES ({len(live)}):")
    for item_name, _, data in live:
        print(
            f"  {item_name}: {data.get('agent_id')} @ {data.get('branch')} (hb: {data.get('heartbeat_at')})"
        )

    print(f"\nSTALE LEASES ({len(stale)}):")
    for item_name, _, data in stale:
        print(
            f"  {item_name}: {data.get('agent_id')} @ {data.get('branch')} (hb: {data.get('heartbeat_at')})"
        )

    if reap:
        for _, lease_file, _ in stale:
            lease_file.unlink(missing_ok=True)
        print(f"\nREAPED {len(stale)} stale lease(s)")

    return 0


def main():
    """Parse CLI and dispatch subcommands."""
    if len(sys.argv) < 2:
        print("Usage: agent_claim.py <subcommand> [args]")
        print(
            "  claim <item> [--agent-id X] [--worktree P] [--branch B] [--stale-hours N] [--no-preflight]"
        )
        print("  heartbeat <item>")
        print("  release <item> [--status merged|abandoned]")
        print("  census [--reap]")
        sys.exit(1)

    subcommand = sys.argv[1]

    if subcommand == "claim":
        if len(sys.argv) < 3:
            print("Usage: agent_claim.py claim <item> [options]")
            sys.exit(1)
        item = sys.argv[2]

        agent_id = "claude"
        if "--agent-id" in sys.argv:
            idx = sys.argv.index("--agent-id")
            if idx + 1 < len(sys.argv):
                agent_id = sys.argv[idx + 1]

        worktree = "."
        if "--worktree" in sys.argv:
            idx = sys.argv.index("--worktree")
            if idx + 1 < len(sys.argv):
                worktree = sys.argv[idx + 1]

        branch = "main"
        if "--branch" in sys.argv:
            idx = sys.argv.index("--branch")
            if idx + 1 < len(sys.argv):
                branch = sys.argv[idx + 1]

        stale_hours = 4
        if "--stale-hours" in sys.argv:
            idx = sys.argv.index("--stale-hours")
            if idx + 1 < len(sys.argv):
                try:
                    stale_hours = int(sys.argv[idx + 1])
                except ValueError:
                    print("Invalid --stale-hours value")
                    sys.exit(1)

        no_preflight = "--no-preflight" in sys.argv

        sys.exit(cmd_claim(item, agent_id, worktree, branch, stale_hours, no_preflight))

    elif subcommand == "heartbeat":
        if len(sys.argv) < 3:
            print("Usage: agent_claim.py heartbeat <item>")
            sys.exit(1)
        item = sys.argv[2]
        sys.exit(cmd_heartbeat(item))

    elif subcommand == "release":
        if len(sys.argv) < 3:
            print("Usage: agent_claim.py release <item> [--status merged|abandoned]")
            sys.exit(1)
        item = sys.argv[2]
        status = "merged"
        if "--status" in sys.argv:
            idx = sys.argv.index("--status")
            if idx + 1 < len(sys.argv):
                status = sys.argv[idx + 1]
        sys.exit(cmd_release(item, status))

    elif subcommand == "census":
        reap = "--reap" in sys.argv
        sys.exit(cmd_census(reap))

    else:
        print(f"Unknown subcommand: {subcommand}")
        sys.exit(1)


if __name__ == "__main__":
    main()
