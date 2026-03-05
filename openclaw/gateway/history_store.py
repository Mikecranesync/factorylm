"""Persist conversation history to JSON file.

Survives service restarts. Called from TelegramAdapter on every message.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

HISTORY_FILE = Path("/tmp/openclaw_chat_history.json")
MAX_HISTORY_PER_USER = 50  # Keep last N messages per user
HISTORY_TTL = 86400  # 24 hours


def load_history(user_id: str) -> list[dict[str, Any]]:
    """Load conversation history for a user."""
    try:
        if not HISTORY_FILE.exists():
            return []
        data = json.loads(HISTORY_FILE.read_text())
        entries = data.get(str(user_id), [])
        # Purge stale entries
        now = time.time()
        return [e for e in entries if now - e.get("ts", 0) < HISTORY_TTL]
    except Exception:
        logger.warning("Failed to load chat history", exc_info=True)
        return []


def append_message(user_id: str, role: str, content: str) -> None:
    """Append a message to the user's conversation history."""
    try:
        data: dict[str, list] = {}
        if HISTORY_FILE.exists():
            data = json.loads(HISTORY_FILE.read_text())

        uid = str(user_id)
        history = data.get(uid, [])
        history.append({"role": role, "content": content, "ts": time.time()})

        # Trim to max
        if len(history) > MAX_HISTORY_PER_USER:
            history = history[-MAX_HISTORY_PER_USER:]

        data[uid] = history
        HISTORY_FILE.write_text(json.dumps(data, indent=2))
    except Exception:
        logger.warning("Failed to save chat history", exc_info=True)


def clear_history(user_id: str) -> None:
    """Clear conversation history for a user."""
    try:
        if not HISTORY_FILE.exists():
            return
        data = json.loads(HISTORY_FILE.read_text())
        data.pop(str(user_id), None)
        HISTORY_FILE.write_text(json.dumps(data, indent=2))
    except Exception:
        logger.warning("Failed to clear chat history", exc_info=True)
