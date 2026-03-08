"""Production gist agent loop — poll → dispatch → respond via gist comment.

Entry point:
    python -m openclaw.gist_agent_loop

Environment variables:
    GIST_POLL_INTERVAL  — seconds between poll cycles (default 30)
    GIST_OWNER_ID       — Telegram user ID for the bot owner
    GIST_SEEN_FILE      — path for seen-comments state (default from gist_poller)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import sys
from pathlib import Path
from typing import Any

from openclaw.gist_dispatch import process_gist_notification
from openclaw.gist_poller import poll_all_gists
from openclaw.gist_responder import notify_channels, post_gist_comment
from openclaw.messages.models import InboundMessage, OutboundMessage
from openclaw.troubleshoot.engine import TreeRunner
from openclaw.troubleshoot.integration import register_troubleshoot, session_dispatch
from openclaw.troubleshoot.models import TroubleshootTree
from openclaw.types import Intent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

POLL_INTERVAL = int(os.environ.get("GIST_POLL_INTERVAL", "30"))
OWNER_ID = os.environ.get("GIST_OWNER_ID", "8445149012")
TREES_DIR = Path(__file__).parent / "troubleshoot" / "trees"


# ── Minimal registry for standalone operation ────────────────────────────────

class _MiniRegistry:
    """Lightweight skill registry — just enough for troubleshoot + session_dispatch."""

    def __init__(self) -> None:
        self._skills: dict[Intent, Any] = {}

    def register(self, intent: Intent, skill: Any) -> None:
        self._skills[intent] = skill

    def get(self, intent: Intent) -> Any | None:
        return self._skills.get(intent)


# ── Tree loading (DB first, JSON fallback) ───────────────────────────────────

def _load_trees() -> list[TroubleshootTree]:
    """Load troubleshoot trees: try DB first, fall back to JSON files."""
    try:
        from openclaw.troubleshoot.store import load_all_trees
        trees = load_all_trees()
        if trees:
            return trees
    except Exception:
        logger.info("DB not available for trees — falling back to JSON files")

    trees = []
    if TREES_DIR.is_dir():
        for json_file in sorted(TREES_DIR.glob("*.json")):
            try:
                data = json.loads(json_file.read_text(encoding="utf-8"))
                trees.append(TroubleshootTree.from_json(data))
            except Exception:
                logger.warning("Failed to load tree %s", json_file.name, exc_info=True)
        logger.info("Loaded %d trees from JSON files", len(trees))
    return trees


# ── Wiring: build dispatch and notify callables ─────────────────────────────

def _build_pipeline() -> tuple[Any, _MiniRegistry]:
    """Initialize TreeRunner, register TroubleshootSkill, return (runner, registry)."""
    registry = _MiniRegistry()
    runner = register_troubleshoot(registry)
    if runner is None:
        # Manual setup if register_troubleshoot failed (e.g. missing DB)
        trees = _load_trees()
        runner = TreeRunner()
        runner.load_trees(trees)
        try:
            from openclaw.troubleshoot.skill import TroubleshootSkill
            skill = TroubleshootSkill(runner)
            registry.register(Intent.TROUBLESHOOT, skill)
        except Exception:
            logger.warning("Could not register TroubleshootSkill", exc_info=True)
    return runner, registry


async def _make_dispatch(registry: _MiniRegistry):
    """Build the dispatch callable that wires into session_dispatch + skill registry."""

    async def dispatch(msg: InboundMessage) -> OutboundMessage:
        # Try session dispatch first (active troubleshoot session)
        session_resp = await session_dispatch(msg, registry, context=None)
        if session_resp is not None:
            return session_resp

        # Fall through to troubleshoot skill directly
        skill = registry.get(Intent.TROUBLESHOOT)
        if skill is not None:
            return await skill.handle(msg, context=None)

        # No skill available — return a basic response
        return OutboundMessage(
            channel=msg.channel,
            user_id=msg.user_id,
            text="Received your note but no troubleshooting skills are loaded.",
        )

    return dispatch


def _make_notify(notify_fns: list | None = None):
    """Build the two-step notify: post gist comment → notify channels with hotlink."""

    channel_fns = notify_fns or []

    async def notify(text: str, *, gist_id: str = "", wo_id: str = "") -> None:
        if gist_id:
            comment_url = await post_gist_comment(gist_id, text)
            if comment_url and channel_fns:
                await notify_channels(gist_id, wo_id, comment_url, channel_fns)
            elif comment_url:
                logger.info("Gist comment posted: %s (no channel notifiers configured)", comment_url)
        else:
            # Fallback: just log (no gist context)
            logger.info("Notify (no gist): %s", text[:200])

    return notify


# ── Main loop ────────────────────────────────────────────────────────────────

async def _poll_loop(
    dispatch,
    runner: TreeRunner,
    registry: _MiniRegistry,
    notify_fns: list | None = None,
) -> None:
    """Run the poll → dispatch → respond loop until cancelled."""
    logger.info(
        "Gist agent loop started — polling every %ds, owner=%s",
        POLL_INTERVAL, OWNER_ID,
    )

    while True:
        try:
            notifications = await asyncio.get_running_loop().run_in_executor(
                None, poll_all_gists,
            )
            if notifications:
                logger.info("Poll cycle: %d new notification(s)", len(notifications))
            else:
                logger.debug("Poll cycle: no new notifications")

            for notif in notifications:
                try:
                    gist_id = notif.get("gist_id", "")
                    wo_id = notif.get("wo_id", "")

                    # Build a per-notification notify that includes gist context
                    base_notify = _make_notify(notify_fns)

                    async def _notify_with_context(
                        text: str,
                        _gid=gist_id,
                        _woid=wo_id,
                        _base=base_notify,
                    ) -> None:
                        await _base(text, gist_id=_gid, wo_id=_woid)

                    await process_gist_notification(
                        notif, dispatch, _notify_with_context, OWNER_ID,
                    )
                except Exception:
                    logger.exception(
                        "Failed to process notification for %s comment %s",
                        notif.get("wo_id", "?"), notif.get("comment_id", "?"),
                    )

        except Exception:
            logger.exception("Poll cycle failed")

        await asyncio.sleep(POLL_INTERVAL)


async def main(notify_fns: list | None = None) -> None:
    """Entry point — initialize pipeline and run the poll loop."""
    runner, registry = _build_pipeline()
    dispatch = await _make_dispatch(registry)

    # Handle graceful shutdown
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _signal_handler() -> None:
        logger.info("Shutdown signal received")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _signal_handler)
        except NotImplementedError:
            # Windows doesn't support add_signal_handler
            pass

    poll_task = asyncio.create_task(_poll_loop(dispatch, runner, registry, notify_fns))

    try:
        await stop_event.wait()
    except KeyboardInterrupt:
        pass
    finally:
        poll_task.cancel()
        try:
            await poll_task
        except asyncio.CancelledError:
            pass
        logger.info("Gist agent loop stopped")


if __name__ == "__main__":
    asyncio.run(main())
