"""Deterministic troubleshooting engine — Layer 0 guided diagnosis."""

from openclaw.troubleshoot.engine import TreeRunner
from openclaw.troubleshoot.models import TroubleshootSession, TroubleshootTree, TreeResponse

__all__ = [
    "TreeRunner",
    "TroubleshootSession",
    "TroubleshootTree",
    "TreeResponse",
    "register_troubleshoot",
    "session_dispatch",
]


def register_troubleshoot(registry) -> TreeRunner | None:
    """Register TroubleshootSkill. Lazy import to avoid pulling VPS-only deps."""
    from openclaw.troubleshoot.integration import register_troubleshoot as _reg
    return _reg(registry)


def session_dispatch(message, registry, context):
    """Session-aware dispatch middleware. Lazy import to avoid pulling VPS-only deps."""
    from openclaw.troubleshoot.integration import session_dispatch as _sd
    return _sd(message, registry, context)
