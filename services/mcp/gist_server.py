"""MCP server for GitHub Gist operations.

Exposes tools for listing, reading, commenting on, and polling gists.
Uses httpx for GitHub REST API calls. Token resolution order:
  GITHUB_TOKEN env → GH_TOKEN env → `gh auth token` subprocess.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

app = FastMCP("factorylm-gist")

# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def _resolve_token() -> str | None:
    """Resolve GitHub token from env or gh CLI."""
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        return token

    gh = shutil.which("gh")
    if not gh:
        win_default = r"C:\Program Files\GitHub CLI\gh.exe"
        if os.path.isfile(win_default):
            gh = win_default

    if gh:
        try:
            result = subprocess.run(
                [gh, "auth", "token"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except Exception:
            pass

    return None


def _get_client() -> httpx.Client:
    """Create an httpx client with GitHub auth headers."""
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = _resolve_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return httpx.Client(
        base_url="https://api.github.com",
        headers=headers,
        timeout=15.0,
    )


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@app.tool()
def list_gists(limit: int = 30) -> list[dict[str, Any]]:
    """List recent gists for the authenticated user.

    Returns gist ID, description, whether it's a WO gist, file names, and URL.
    """
    with _get_client() as client:
        resp = client.get("/gists", params={"per_page": min(limit, 100)})
        resp.raise_for_status()

    gists = []
    for g in resp.json():
        gists.append({
            "id": g["id"],
            "description": g.get("description", ""),
            "is_work_order": "[Jarvis Work Order]" in (g.get("description") or ""),
            "files": list((g.get("files") or {}).keys()),
            "url": g["html_url"],
            "updated_at": g.get("updated_at", ""),
        })
    return gists


@app.tool()
def get_gist(gist_id: str) -> dict[str, Any]:
    """Get full metadata for a single gist."""
    with _get_client() as client:
        resp = client.get(f"/gists/{gist_id}")
        resp.raise_for_status()

    g = resp.json()
    return {
        "id": g["id"],
        "description": g.get("description", ""),
        "files": {
            name: {
                "filename": f.get("filename"),
                "language": f.get("language"),
                "size": f.get("size"),
                "content": f.get("content", "")[:2000],
            }
            for name, f in (g.get("files") or {}).items()
        },
        "url": g["html_url"],
        "created_at": g.get("created_at", ""),
        "updated_at": g.get("updated_at", ""),
        "owner": (g.get("owner") or {}).get("login", "unknown"),
    }


@app.tool()
def read_comments(gist_id: str) -> list[dict[str, Any]]:
    """Get all comments on a gist."""
    with _get_client() as client:
        resp = client.get(f"/gists/{gist_id}/comments")
        resp.raise_for_status()

    comments = []
    for c in resp.json():
        comments.append({
            "id": c["id"],
            "user": (c.get("user") or {}).get("login", "unknown"),
            "body": c.get("body", ""),
            "created_at": c.get("created_at", ""),
        })
    return comments


@app.tool()
def post_comment(gist_id: str, body: str) -> dict[str, Any]:
    """Post a comment to a gist."""
    with _get_client() as client:
        resp = client.post(
            f"/gists/{gist_id}/comments",
            json={"body": body},
        )
        resp.raise_for_status()

    c = resp.json()
    return {
        "id": c["id"],
        "url": c.get("html_url", ""),
        "body": c.get("body", ""),
    }


@app.tool()
def poll_new() -> list[dict[str, Any]]:
    """Run one poll cycle and return new notifications.

    Uses openclaw.gist_poller.poll_all_gists() under the hood.
    """
    import sys
    # Ensure monorepo root is on path for imports
    monorepo = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if monorepo not in sys.path:
        sys.path.insert(0, monorepo)

    from openclaw.gist_poller import poll_all_gists
    return poll_all_gists()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app.run()
