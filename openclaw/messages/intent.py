"""Intent detection for incoming messages and photos.

Classifies user messages into intents that determine which pipeline
to route them through.
"""

from __future__ import annotations

from openclaw.types import Intent

# Keyword patterns per intent (lowercase, matched against message text + caption)
INTENT_PATTERNS: dict[str, list[str]] = {
    Intent.WIRING_RECONSTRUCT: [
        "reconstruct",
        "rebuild",
        "missing prints",
        "no drawings",
        "photo to diagram",
        "rebuild wiring",
        "trace wiring",
        "wiring diagram",
        "panel drawing",
        "no prints",
    ],
    Intent.KB_ENRICH_COMPONENT: [
        "component tag",
        "nameplate",
        "unknown part",
        "new component",
        "what is this",
        "identify",
        "data plate",
        "close-up",
        "close up",
        "model number",
        "part number",
    ],
    Intent.DIAGNOSE: [
        "why",
        "stopped",
        "diagnose",
        "fault",
        "wrong",
        "error",
        "alarm",
        "trip",
    ],
    Intent.STATUS: [
        "status",
        "health",
        "online",
        "connected",
        "running",
    ],
    Intent.IO: [
        "show io",
        "live io",
        "plc",
        "tags",
        "inputs",
        "outputs",
    ],
}


def classify_intent(
    text: str,
    *,
    has_photo: bool = False,
    has_active_project: bool = False,
) -> Intent:
    """Classify a message into an intent.

    Args:
        text: Message text or photo caption (may be empty).
        has_photo: Whether the message includes a photo.
        has_active_project: Whether there's an active WiringProject for this chat.

    Returns:
        The most likely Intent.
    """
    normalized = text.lower().strip()

    # Score each intent by keyword matches
    scores: dict[Intent, int] = {}
    for intent_str, keywords in INTENT_PATTERNS.items():
        intent = Intent(intent_str) if isinstance(intent_str, str) else intent_str
        score = sum(1 for kw in keywords if kw in normalized)
        if score > 0:
            scores[intent] = score

    # If we have explicit keyword matches, return the highest-scoring intent
    if scores:
        best = max(scores, key=lambda k: scores[k])
        # Special case: if active project and photo, always include reconstruction
        if has_active_project and has_photo and best == Intent.KB_ENRICH_COMPONENT:
            return Intent.WIRING_RECONSTRUCT
        return best

    # Default behavior for photos without keywords
    if has_photo:
        if has_active_project:
            return Intent.WIRING_RECONSTRUCT
        return Intent.KB_ENRICH_COMPONENT

    return Intent.GENERAL


def classify_photo_intent(
    caption: str,
    *,
    has_active_project: bool = False,
) -> list[Intent]:
    """Classify a photo message, potentially returning multiple intents.

    Photos always get KB_ENRICH_COMPONENT. If there's an active project
    or the caption indicates reconstruction, WIRING_RECONSTRUCT is added.

    Returns:
        List of intents to process (may be 1 or 2).
    """
    intents = [Intent.KB_ENRICH_COMPONENT]  # Every photo enriches

    primary = classify_intent(
        caption,
        has_photo=True,
        has_active_project=has_active_project,
    )

    if primary == Intent.WIRING_RECONSTRUCT:
        intents.append(Intent.WIRING_RECONSTRUCT)
    elif has_active_project:
        intents.append(Intent.WIRING_RECONSTRUCT)

    return intents
