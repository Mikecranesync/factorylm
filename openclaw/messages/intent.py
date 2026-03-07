"""Intent detection for incoming messages and photos.

Two-stage classifier:
1. Keyword match (fast, free, deterministic) — handles clear-cut messages
2. LLM fallback (semantic, costs tokens) — handles ambiguous natural language

The LLM fallback is opt-in via use_llm_fallback=True and requires GROQ_API_KEY.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from openclaw.types import Intent

log = logging.getLogger("openclaw.intent")

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
        "noise",
        "vibrat",
        "overheat",
        "leak",
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
    Intent.TROUBLESHOOT: [
        "troubleshoot",
        "walk me through",
        "step by step",
        "guide me",
        "how do i fix",
        "/troubleshoot",
    ],
}

_INTENT_NAMES = [i.value for i in Intent]

_LLM_CLASSIFY_PROMPT = (
    "You are an intent classifier for an industrial maintenance AI system. "
    "Classify the technician's message into exactly ONE of these intents:\n"
    "- DIAGNOSE: asking why something is broken, faulted, stopped, or behaving wrong\n"
    "- TROUBLESHOOT: wants step-by-step guided repair or walkthrough\n"
    "- STATUS: asking about machine/system health or connectivity\n"
    "- IO: wants to see live PLC tags, inputs, outputs, or sensor readings\n"
    "- WIRING_RECONSTRUCT: wants to rebuild or trace wiring diagrams\n"
    "- KB_ENRICH_COMPONENT: identifying a component from a photo or nameplate\n"
    "- GENERAL: casual conversation, greetings, or anything that doesn't fit above\n\n"
    'Respond with ONLY a JSON object: {"intent": "INTENT_NAME", "confidence": 0.0-1.0}\n'
)


def _keyword_classify(normalized: str) -> dict[Intent, int]:
    """Score intents by keyword matches. Returns {intent: score}."""
    scores: dict[Intent, int] = {}
    for intent_str, keywords in INTENT_PATTERNS.items():
        intent = Intent(intent_str) if isinstance(intent_str, str) else intent_str
        score = sum(1 for kw in keywords if kw in normalized)
        if score > 0:
            scores[intent] = score
    return scores


def _llm_classify(text: str) -> Intent | None:
    """Classify via Groq LLM. Returns Intent or None on failure."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return None

    try:
        import requests

        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {"role": "system", "content": _LLM_CLASSIFY_PROMPT},
                    {"role": "user", "content": text},
                ],
                "max_tokens": 50,
                "temperature": 0,
                "response_format": {"type": "json_object"},
            },
            timeout=5,
        )
        if r.status_code != 200:
            log.warning("LLM classify returned %d", r.status_code)
            return None

        content = r.json()["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        intent_name = parsed.get("intent", "").upper()
        if intent_name in _INTENT_NAMES:
            log.info("LLM classified '%s' → %s (conf=%.2f)", text[:40], intent_name, parsed.get("confidence", 0))
            return Intent(intent_name)
        return None
    except Exception as e:
        log.warning("LLM classify failed: %s", e)
        return None


def classify_intent(
    text: str,
    *,
    has_photo: bool = False,
    has_active_project: bool = False,
    use_llm_fallback: bool = False,
) -> Intent:
    """Classify a message into an intent.

    Two-stage: keyword match first (free), then optional LLM fallback
    for ambiguous messages.

    Args:
        text: Message text or photo caption (may be empty).
        has_photo: Whether the message includes a photo.
        has_active_project: Whether there's an active WiringProject for this chat.
        use_llm_fallback: If True, use LLM when keywords don't match.

    Returns:
        The most likely Intent.
    """
    normalized = text.lower().strip()

    # Stage 1: keyword match (fast, free)
    scores = _keyword_classify(normalized)

    if scores:
        best = max(scores, key=lambda k: scores[k])
        if has_active_project and has_photo and best == Intent.KB_ENRICH_COMPONENT:
            return Intent.WIRING_RECONSTRUCT
        return best

    # Default behavior for photos without keywords
    if has_photo:
        if has_active_project:
            return Intent.WIRING_RECONSTRUCT
        return Intent.KB_ENRICH_COMPONENT

    # Stage 2: LLM fallback for ambiguous text (no keyword hits, no photo)
    if use_llm_fallback and normalized:
        llm_result = _llm_classify(text)
        if llm_result is not None:
            return llm_result

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
