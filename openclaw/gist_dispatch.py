"""Gist comment dispatch — bridge between poller output and agentic pipeline.

Routes note-type gist comments through dispatch (intent → skill → response)
while command-type comments bypass dispatch and notify directly.
"""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, Optional

from openclaw.messages.models import InboundMessage
from openclaw.types import Channel

logger = logging.getLogger(__name__)


async def process_gist_notification(
    notif: dict[str, Any],
    dispatch: Optional[Callable[[InboundMessage], Awaitable[Any]]],
    notify: Callable[[str], Awaitable[None]],
    owner_id: str,
) -> None:
    """Process a single gist notification from poll_all_gists().

    Args:
        notif: Notification dict with keys: wo_id, gist_id, type, user,
               comment_id, and either field/value (command) or body (note).
        dispatch: Async callable (InboundMessage -> response) for agentic
                  processing. Response must have a .text attribute.
                  Pass None to skip dispatch and just notify.
        notify: Async callable (str -> None) for sending notifications.
        owner_id: User ID string for the bot owner.
    """
    wo_id = notif["wo_id"]
    gist_id = notif["gist_id"]
    user = notif["user"]
    comment_id = notif["comment_id"]

    if notif["type"] == "command":
        await notify(
            f"WO {wo_id} updated: {notif['field']} -> {notif['value']} (by {user})"
        )
        return

    # note-type
    body = notif["body"]

    if dispatch is not None:
        try:
            msg = InboundMessage(
                id=f"gist-{comment_id}",
                channel=Channel.TELEGRAM,
                user_id=owner_id,
                user_name=user,
                text=f"[WO {wo_id}] {body}",
                metadata={
                    "source": "gist_comment",
                    "gist_id": gist_id,
                    "wo_id": wo_id,
                },
            )
            response = await dispatch(msg)
            await notify(f"Re: {wo_id}\n{response.text}")
        except Exception:
            logger.warning(
                "Dispatch failed for gist comment %s on %s",
                comment_id, wo_id, exc_info=True,
            )
            await notify(f"Comment on {wo_id} by {user}:\n{body[:200]}")
    else:
        await notify(f"Comment on {wo_id} by {user}:\n{body[:200]}")
