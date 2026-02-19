"""Integration helpers: register skill and session-aware dispatch middleware.

Usage in app.py startup:

    from openclaw.troubleshoot.integration import register_troubleshoot, session_dispatch

    # During startup, after other skills registered:
    register_troubleshoot(registry)

    # In dispatch(), BEFORE intent classification:
    session_response = await session_dispatch(message, registry, context)
    if session_response:
        return session_response

The session_dispatch middleware is CRITICAL — without it, numeric replies
("2") to troubleshoot questions get classified as GENERAL and miss the
active session.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from openclaw.troubleshoot.engine import TreeRunner
from openclaw.types import Intent

if TYPE_CHECKING:
    from openclaw.messages.models import InboundMessage, OutboundMessage
    from openclaw.skills.base import SkillContext

logger = logging.getLogger(__name__)

# Module-level runner reference so session_dispatch can find it
_runner: TreeRunner | None = None


def register_troubleshoot(registry) -> TreeRunner | None:
    """Register TroubleshootSkill in the skill registry.

    Call during app startup after other builtins are registered.
    Returns the TreeRunner instance (or None on failure).
    """
    global _runner

    try:
        from openclaw.troubleshoot.skill import TroubleshootSkill
        from openclaw.troubleshoot.store import load_all_trees

        trees = load_all_trees()
        runner = TreeRunner()
        runner.load_trees(trees)
        skill = TroubleshootSkill(runner)
        registry.register(Intent.TROUBLESHOOT, skill)

        # Share runner with DiagnoseSkill for escalation offers
        diagnose_skill = registry.get(Intent.DIAGNOSE)
        if diagnose_skill:
            diagnose_skill._troubleshoot_runner = runner

        _runner = runner
        logger.info("TroubleshootSkill registered with %d trees", len(trees))
        return runner

    except Exception:
        logger.exception("Failed to register TroubleshootSkill — continuing without it")
        return None


async def session_dispatch(
    message: InboundMessage,
    registry,
    context: SkillContext,
) -> OutboundMessage | None:
    """Session-aware dispatch middleware for troubleshoot sessions.

    Call this BEFORE intent classification in the main dispatch() function.
    If the user has an active troubleshoot session, routes directly to the
    TroubleshootSkill — bypassing intent classification entirely.

    Returns an OutboundMessage if handled, or None to continue normal dispatch.

    Why this is needed:
        When a user replies "2" to a troubleshoot question, the intent
        classifier sees a bare number and returns GENERAL. The session
        check must happen first to intercept these replies.
    """
    if _runner is None:
        return None

    if not _runner.has_active_session(message.user_id):
        return None

    # User has an active session — route to TroubleshootSkill
    skill = registry.get(Intent.TROUBLESHOOT)
    if skill is None:
        return None

    try:
        return await skill.handle(message, context)
    except Exception:
        logger.exception("Troubleshoot session dispatch failed for user %s", message.user_id)
        return None
