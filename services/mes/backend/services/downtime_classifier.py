"""Downtime reason classifier — maps free-text descriptions to reason codes.

Pure function, no I/O, no LLM required.
Used when MIRA or an operator submits a plain-English description of why
a line is down (e.g. "the conveyor is jammed" → JAM).

Keyword priority table (first match wins — order matters):
  E_STOP            estop, e-stop, emergency stop
  MAINT_PM          pm, preventive, scheduled maint, planned maint
  MAINT_BREAKDOWN   breakdown, broken, failed, fault (generic)
  CHANGEOVER_TOOLING tooling, tool change
  CHANGEOVER_PRODUCT changeover, product change, switchover, new run
  JAM               jam, jammed, stuck, snagged, wedged
  STARVED_MATERIAL  starved, no material, empty, feed, material
  BLOCKED_DOWNSTREAM blocked, downstream, full, backing up
  QUALITY_HOLD      quality, hold, inspection, reject, rework
  OVERLOAD          overload, overcurrent
  OVERHEAT          overheat, hot, thermal, temperature
  SENSOR_FAIL       sensor, proximity, photoelectric, switch
  COMMS_FAIL        comms, communication, timeout, network, modbus
  UNKNOWN           (fallback)

Returns:
  (reason_code: str, confidence: str)
  confidence = "high" if keyword found, "low" if fallback to UNKNOWN.
"""

import re
from typing import Tuple

# ── Keyword map (ordered — first match wins) ──────────────────────────────────

_RULES = [
    ("E_STOP",              ["estop", "e-stop", "e stop", "emergency stop"]),
    ("MAINT_PM",            ["preventive maint", "planned maint", "scheduled maint",
                             r"\bpm\b"]),
    ("MAINT_BREAKDOWN",     ["breakdown", "broke down", "broken", "out of service"]),
    ("CHANGEOVER_TOOLING",  ["tooling change", "tool change", "new tooling", "tooling"]),
    ("CHANGEOVER_PRODUCT",  ["changeover", "product change", "switchover", "new run",
                             "new product"]),
    ("JAM",                 ["jammed", "jam", "stuck", "snagged", "wedged", "tangled"]),
    ("STARVED_MATERIAL",    ["starved", "no material", "out of material", "empty",
                             "no stock", "feed empty"]),
    ("BLOCKED_DOWNSTREAM",  ["blocked", "downstream", "backing up", "full", "backlog"]),
    ("QUALITY_HOLD",        ["quality hold", "quality issue", "hold", "inspection",
                             "reject", "rework", "scrap"]),
    ("OVERLOAD",            ["overload", "overcurrent", "tripped"]),
    ("OVERHEAT",            ["overheat", "overheating", "hot", "thermal", "temperature"]),
    ("SENSOR_FAIL",         ["sensor failed", "sensor failure", "sensor fault",
                             "sensor", "proximity", "photoelectric", "limit switch",
                             "detector"]),
    ("COMMS_FAIL",          ["comms", "communication", "timeout", "network", "modbus",
                             "lost connection"]),
]


def classify_reason(text: str) -> Tuple[str, str]:
    """Classify free-text downtime description into a reason code.

    Args:
        text: Free-text description from an operator or MIRA chat.

    Returns:
        (reason_code, confidence) — confidence is "high" or "low".
        Always returns a valid reason_code string (fallback: "UNKNOWN").

    Examples:
        >>> classify_reason("the conveyor is jammed")
        ('JAM', 'high')
        >>> classify_reason("scheduled PM window")
        ('MAINT_PM', 'high')
        >>> classify_reason("some weird thing happened")
        ('UNKNOWN', 'low')
    """
    if not text or not text.strip():
        return ("UNKNOWN", "low")

    normalised = text.lower().strip()

    for reason_code, patterns in _RULES:
        for pattern in patterns:
            # Treat pattern as regex if it starts with \b, else literal substring
            if pattern.startswith(r"\b") or pattern.startswith("("):
                if re.search(pattern, normalised):
                    return (reason_code, "high")
            else:
                if pattern in normalised:
                    return (reason_code, "high")

    return ("UNKNOWN", "low")
