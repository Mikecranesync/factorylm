"""VPS patch: Register TroubleshootSkill and add session-aware dispatch.

This file contains executable functions to wire up the troubleshoot engine.
Import and call from app.py during startup.

Usage in app.py:
    from openclaw.troubleshoot.integration import register_troubleshoot, session_dispatch

    # During startup, after other skills are registered:
    register_troubleshoot(registry)

    # In dispatch(), BEFORE intent classification:
    session_response = await session_dispatch(message, registry, context)
    if session_response:
        return session_response
"""
