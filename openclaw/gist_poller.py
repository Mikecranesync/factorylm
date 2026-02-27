"""Gist comment poller — discovers work-order gists, fetches new comments,
parses commands (status/priority/assign/category), and returns notifications."""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

SEEN_FILE = Path(os.environ.get(
    "GIST_SEEN_FILE", "/opt/openclaw/data/seen_comments.json"
))

# Regex for structured commands in comment body
_CMD_RE = re.compile(
    r"^\s*(status|priority|assign|category)\s*:\s*(.+)$",
    re.IGNORECASE | re.MULTILINE,
)


def _gh_exe() -> str:
    """Resolve the gh CLI executable path.

    Uses shutil.which first; falls back to the default Windows install path.
    """
    found = shutil.which("gh")
    if found:
        return found
    win_default = r"C:\Program Files\GitHub CLI\gh.exe"
    if os.path.isfile(win_default):
        return win_default
    return "gh"  # last resort — let subprocess raise if missing


def _load_seen() -> dict[str, dict]:
    """Load the seen-comments state from disk."""
    if not SEEN_FILE.exists():
        return {}
    try:
        return json.loads(SEEN_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        logger.warning("Corrupt seen_comments.json — starting fresh")
        return {}


def _save_seen(seen: dict[str, dict]) -> None:
    """Persist seen-comments state to disk."""
    SEEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    SEEN_FILE.write_text(json.dumps(seen, indent=2), encoding="utf-8")


def parse_comment_command(body: str) -> dict[str, Any]:
    """Parse a gist comment body for structured commands.

    Returns:
        {"type": "command", "field": <field>, "value": <value>}  — for recognized commands
        {"type": "note", "raw": <body>}                          — for free-text comments
    """
    m = _CMD_RE.search(body)
    if m:
        return {
            "type": "command",
            "field": m.group(1).lower(),
            "value": m.group(2).strip(),
        }
    return {"type": "note", "raw": body.strip()}


def list_work_order_gists() -> list[dict[str, str]]:
    """List recent gists that match the Jarvis Work Order convention.

    Returns list of {"id": ..., "description": ...}.
    """
    result = subprocess.run(
        [_gh_exe(), "gist", "list", "--limit", "50"],
        capture_output=True, text=True, timeout=10,
    )
    if result.returncode != 0:
        logger.error("gh gist list failed: %s", result.stderr)
        return []

    gists: list[dict[str, str]] = []
    for line in result.stdout.strip().splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        gist_id = parts[0].strip()
        description = parts[1].strip()
        if "[Jarvis Work Order]" in description:
            gists.append({"id": gist_id, "description": description})
    return gists


def list_watched_gists() -> list[dict[str, str]]:
    """Fetch metadata for explicitly watched gist IDs (from GIST_WATCH_IDS env var).

    Returns list of {"id": ..., "description": ...}.
    """
    raw = os.environ.get("GIST_WATCH_IDS", "")
    if not raw.strip():
        return []

    ids = [gid.strip() for gid in raw.split(",") if gid.strip()]
    gists: list[dict[str, str]] = []

    for gist_id in ids:
        result = subprocess.run(
            [_gh_exe(), "api", f"/gists/{gist_id}"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            logger.warning("Failed to fetch watched gist %s: %s", gist_id, result.stderr)
            continue
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            logger.warning("Invalid JSON for watched gist %s", gist_id)
            continue

        gists.append({
            "id": gist_id,
            "description": data.get("description", "") or f"(watched gist {gist_id[:8]})",
        })

    return gists


def fetch_gist_comments(gist_id: str) -> list[dict[str, Any]]:
    """Fetch comments for a single gist via gh API.

    Returns list of {"id": int, "body": str, "user": str, "created_at": str}.
    """
    result = subprocess.run(
        [_gh_exe(), "api", f"/gists/{gist_id}/comments"],
        capture_output=True, text=True, timeout=10,
    )
    if result.returncode != 0:
        logger.error("gh api gist comments failed for %s: %s", gist_id, result.stderr)
        return []

    try:
        raw = json.loads(result.stdout)
    except json.JSONDecodeError:
        logger.error("Invalid JSON from gist comments for %s", gist_id)
        return []

    comments: list[dict[str, Any]] = []
    for c in raw:
        comments.append({
            "id": c.get("id", 0),
            "body": c.get("body", ""),
            "user": (c.get("user") or {}).get("login", "unknown"),
            "created_at": c.get("created_at", ""),
        })
    return comments


def _extract_wo_id(description: str) -> str:
    """Extract WO-YYYY-MMDD-NNN from a gist description.

    Falls back to the description itself (truncated) for non-WO gists.
    """
    m = re.search(r"(WO-\d{4}-\d{4}-\d{3})", description)
    if m:
        return m.group(1)
    # Graceful fallback for watched gists without WO convention
    return description[:60] if description else "(no description)"


def poll_all_gists() -> list[dict[str, Any]]:
    """Main entry point — discover gists, fetch new comments, process commands.

    Merges auto-discovered WO gists with explicitly watched gists (GIST_WATCH_IDS).
    Deduplicates by gist ID.

    Returns list of notification dicts:
        {"wo_id": ..., "gist_id": ..., "type": "command"|"note",
         "field": ..., "value": ..., "user": ..., "body": ...}
    """
    seen = _load_seen()
    notifications: list[dict[str, Any]] = []

    # Merge auto-discovered WO gists + explicitly watched gists
    wo_gists = list_work_order_gists()
    watched = list_watched_gists()

    # Deduplicate: WO gists take precedence
    seen_ids = {g["id"] for g in wo_gists}
    for g in watched:
        if g["id"] not in seen_ids:
            wo_gists.append(g)
            seen_ids.add(g["id"])

    gists = wo_gists
    if not gists:
        return notifications

    for gist in gists:
        gist_id = gist["id"]
        wo_id = _extract_wo_id(gist["description"])

        try:
            comments = fetch_gist_comments(gist_id)
        except Exception:
            logger.warning("Failed to fetch comments for %s", gist_id, exc_info=True)
            continue

        if not comments:
            # Track gist even if no comments yet
            if gist_id not in seen:
                seen[gist_id] = {
                    "last_seen_comment_id": 0,
                    "wo_description": gist["description"],
                }
            continue

        last_seen_id = seen.get(gist_id, {}).get("last_seen_comment_id", 0)

        new_comments = [c for c in comments if c["id"] > last_seen_id]
        if not new_comments:
            continue

        for comment in new_comments:
            parsed = parse_comment_command(comment["body"])
            notif: dict[str, Any] = {
                "wo_id": wo_id,
                "gist_id": gist_id,
                "user": comment["user"],
                "comment_id": comment["id"],
            }

            if parsed["type"] == "command":
                notif["type"] = "command"
                notif["field"] = parsed["field"]
                notif["value"] = parsed["value"]

                # Apply the update to the gist
                try:
                    from openclaw.skills.builtin.gist_work_order import (
                        update_work_order_gist,
                    )
                    update_work_order_gist(gist_id, {parsed["field"]: parsed["value"]})
                    logger.info(
                        "Updated %s: %s -> %s (by %s)",
                        wo_id, parsed["field"], parsed["value"], comment["user"],
                    )
                except Exception:
                    logger.warning(
                        "Failed to update gist %s for command %s",
                        gist_id, parsed, exc_info=True,
                    )
            else:
                notif["type"] = "note"
                notif["body"] = comment["body"][:500]

            notifications.append(notif)

        # Update high-water mark
        max_id = max(c["id"] for c in new_comments)
        seen[gist_id] = {
            "last_seen_comment_id": max_id,
            "wo_description": gist["description"],
        }

    _save_seen(seen)
    return notifications
