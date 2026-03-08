"""Safety checks for the autonomous scene learner.

Prevents writes to safety-critical tags and refuses all actions when e-stop is active.
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger("factorylm.learner.safety")

# Tags that must NEVER be written to by the learner
NEVER_WRITE_PATTERNS = [
    "e_stop",
    "emergency",
    "safety",
    "estop",
    "e-stop",
]


def is_safe_to_write(tag_name: str) -> bool:
    """Return True if the tag is safe for the learner to write."""
    lower = tag_name.lower()
    for pattern in NEVER_WRITE_PATTERNS:
        if pattern in lower:
            logger.warning("BLOCKED write to safety tag: %s", tag_name)
            return False
    return True


def check_estop(tags: dict) -> bool:
    """Return True if e-stop is active (writes should be refused).

    Checks common e-stop tag names in the tag snapshot.
    """
    for key, value in tags.items():
        lower = key.lower()
        if ("e_stop" in lower or "estop" in lower or "emergency" in lower):
            if value:
                logger.warning("E-STOP ACTIVE: %s = %s — refusing all writes", key, value)
                return True
    return False


def pre_write_check(tag_name: str, tags: Optional[dict] = None) -> tuple[bool, str]:
    """Combined safety check before any Modbus write.

    Returns (safe, reason). If safe is False, the write must not proceed.
    """
    if not is_safe_to_write(tag_name):
        return False, f"Tag '{tag_name}' matches safety-critical pattern"

    if tags and check_estop(tags):
        return False, "E-stop is active — all writes blocked"

    return True, "OK"
