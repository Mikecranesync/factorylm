# Restored from: main:installers/claude-telegram-bridge/claude_telegram_bridge.py
"""
Claude CLI subprocess bridge — routes text messages to Claude Code.
"""

import asyncio
import logging
import subprocess
import sys
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def find_claude_cli() -> Optional[str]:
    """Find the claude CLI executable on this machine."""
    candidates = [
        "claude",
        str(Path.home() / ".claude" / "claude"),
        str(Path.home() / "AppData" / "Local" / "Programs" / "claude" / "claude.exe"),
        "/usr/local/bin/claude",
    ]
    for candidate in candidates:
        try:
            result = subprocess.run(
                [candidate, "--version"],
                capture_output=True,
                timeout=5,
            )
            if result.returncode == 0:
                return candidate
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    return None


def check_claude_available() -> bool:
    """Startup check: verify Claude CLI is installed and print version."""
    path = find_claude_cli()
    if path is None:
        logger.warning(
            "Claude CLI not found. Text-to-Claude bridge will be unavailable. "
            "Install from https://claude.ai/code"
        )
        return False
    try:
        result = subprocess.run([path, "--version"], capture_output=True, timeout=5)
        version = result.stdout.decode().strip()
        logger.info(f"Claude CLI found: {path} ({version})")
        return True
    except Exception as e:
        logger.warning(f"Claude CLI check failed: {e}")
        return False


async def run_claude(message: str, workspace: Optional[Path] = None, timeout: int = 300) -> str:
    """
    Run claude CLI with a message and return the response.

    Args:
        message: The user message to send to Claude
        workspace: Working directory for Claude (optional)
        timeout: Max seconds to wait (default 5 min)

    Returns:
        Claude's response text, or an error message
    """
    claude_path = find_claude_cli()
    if claude_path is None:
        return "Claude CLI not found. Install from https://claude.ai/code"

    ws = workspace or Path.home() / "jarvis-workspace"
    ws.mkdir(parents=True, exist_ok=True)

    cmd = [claude_path, "--print", message]

    logger.info(f"Running Claude: {message[:60]}...")

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(ws),
        )
        stdout, stderr = await asyncio.wait_for(
            process.communicate(), timeout=timeout
        )

        response = stdout.decode("utf-8", errors="replace").strip()

        if process.returncode != 0:
            error = stderr.decode("utf-8", errors="replace").strip()
            logger.error(f"Claude error: {error}")
            return f"Error: {error[:500]}"

        return response or "Claude returned empty response"

    except asyncio.TimeoutError:
        return f"Claude timed out after {timeout // 60} minutes"
    except FileNotFoundError:
        return "Claude CLI not found. Is it installed?"
    except Exception as e:
        logger.exception("Claude execution error")
        return f"Error: {str(e)[:200]}"
