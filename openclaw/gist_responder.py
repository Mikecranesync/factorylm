"""Gist responder — posts agent responses as gist comments and notifies channels."""

from __future__ import annotations

import asyncio
import json
import logging
import subprocess
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)


async def post_gist_comment(gist_id: str, body: str) -> str | None:
    """Post a comment on a gist via gh api.

    Returns the comment's html_url on success, or None on failure.
    """
    loop = asyncio.get_running_loop()
    try:
        result = await loop.run_in_executor(
            None,
            lambda: subprocess.run(
                [
                    "gh", "api",
                    "--method", "POST",
                    f"/gists/{gist_id}/comments",
                    "-f", f"body={body}",
                ],
                capture_output=True, text=True, timeout=15,
            ),
        )
        if result.returncode != 0:
            logger.error("gh api POST gist comment failed: %s", result.stderr)
            return None

        data = json.loads(result.stdout)
        url = data.get("html_url")
        logger.info("Posted gist comment on %s: %s", gist_id, url)
        return url

    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError) as exc:
        logger.error("Failed to post gist comment on %s: %s", gist_id, exc)
        return None


async def notify_channels(
    gist_id: str,
    wo_id: str,
    comment_url: str,
    notify_fns: list[Callable[[str], Awaitable[None]]],
) -> None:
    """Send hotlink notification to all comms channels (Telegram, etc.).

    Each notify_fn receives a short message with the gist comment URL.
    """
    message = f"WO {wo_id} — new intel posted. See the gist: {comment_url}"
    for fn in notify_fns:
        try:
            await fn(message)
        except Exception:
            logger.warning("Channel notification failed for WO %s", wo_id, exc_info=True)
