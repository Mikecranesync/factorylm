"""Resolve a GitHub token from multiple sources.

Priority order:
  1. GITHUB_TOKEN environment variable (already set, e.g. from .env)
  2. `gh auth token` CLI (uses Windows Credential Manager / macOS Keychain)
  3. `keyring` Python package (if installed)

Returns the token string or empty string if nothing found.
This module has ZERO required dependencies beyond the stdlib.
"""

from __future__ import annotations

import logging
import os
import subprocess

logger = logging.getLogger(__name__)

_KEYRING_SERVICE = "factorylm-github-scraper"
_KEYRING_USERNAME = "github_token"


def load_github_token() -> str:
    """Try every source in priority order. Return token or ''."""

    # 1. Already in env (from .env or parent process)
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if token and token != "your_token_here":
        logger.info("GitHub token loaded from environment variable")
        return token

    # 2. gh CLI (works on Windows, macOS, Linux if gh is installed)
    token = _try_gh_cli()
    if token:
        logger.info("GitHub token loaded from gh CLI")
        return token

    # 3. keyring (optional dependency)
    token = _try_keyring()
    if token:
        logger.info("GitHub token loaded from system keyring")
        return token

    logger.warning("No GitHub token found in any source")
    return ""


def _try_gh_cli() -> str:
    """Run `gh auth token` and return the token, or '' on failure."""
    try:
        result = subprocess.run(
            ["gh", "auth", "token"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return ""


def _try_keyring() -> str:
    """Try the keyring package if installed, or '' on failure."""
    try:
        import keyring  # type: ignore[import-untyped]
        token = keyring.get_password(_KEYRING_SERVICE, _KEYRING_USERNAME)
        return token or ""
    except Exception:
        return ""


def save_to_keyring(token: str) -> bool:
    """Store a token in the system keyring. Returns True on success."""
    try:
        import keyring  # type: ignore[import-untyped]
        keyring.set_password(_KEYRING_SERVICE, _KEYRING_USERNAME, token)
        return True
    except Exception as exc:
        logger.warning("Could not save to keyring: %s", exc)
        return False
