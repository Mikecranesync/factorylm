"""Vision LLM prompt templates for wiring reconstruction.

Each prompt is a function that returns a system+user prompt pair,
parameterized by current project state.
"""

from __future__ import annotations

from openclaw.diagram.symbols import SYMBOL_REGISTRY

# Valid component types for the vision model
VALID_TYPES = ", ".join(sorted(SYMBOL_REGISTRY.keys()))

# IEC 60757 wire color codes
WIRE_COLOR_CODES = "BK (black), BU (blue), BN (brown), GN-YE (green-yellow/earth), RD (red), WH (white), GY (grey), OG (orange), PK (pink), VT (violet)"


def initial_photo_prompt(*, focus_tag: str | None = None) -> tuple[str, str]:
    """Prompt for initial panel photo analysis.

    Returns (system_prompt, user_prompt) to be sent with the image.
    """
    system = (
        "You are an expert industrial electrician analyzing a control panel photograph. "
        "Your task is to identify every visible component, read nameplates, trace wires, "
        "and return structured data. You are precise and only report what you can actually see."
    )

    tag_focus = ""
    if focus_tag:
        tag_focus = (
            f"\n\nFOCUS: Pay special attention to component tagged '{focus_tag}'. "
            f"Extract all visible detail for this component first."
        )

    user = f"""Analyze this control panel photo. Identify every visible component.

For each component, extract:
- tag: The device tag visible on the component or inferred from position (Q1, K1, M1, F1, S0, S1, etc.)
- type: One of [{VALID_TYPES}]
- manufacturer: If visible on nameplate
- part_number: If visible on nameplate
- visible_terminals: List of terminal numbers you can read
- mounting_location: Position in the panel (e.g., "top-left DIN rail", "bottom right")
- confidence: 0.0–1.0 (how certain you are about this identification)

For each traceable wire, extract:
- from: Source as "TAG.TERMINAL" (e.g., "Q1.2")
- to: Destination as "TAG.TERMINAL" (e.g., "K1.1")
- wire_color: IEC color code ({WIRE_COLOR_CODES})
- wire_label: If a ferrule or label is visible
- confidence: 0.0–1.0
{tag_focus}

RESPOND IN JSON ONLY with this structure:
{{
  "components": [
    {{
      "tag": "Q1",
      "type": "circuit_breaker",
      "manufacturer": "Eaton",
      "part_number": "PKZM0-10",
      "visible_terminals": ["1","2","3","4","5","6"],
      "mounting_location": "top-left DIN rail",
      "confidence": 0.8
    }}
  ],
  "connections": [
    {{
      "from": "Q1.2",
      "to": "K1.1",
      "wire_color": "BK",
      "wire_label": "W1",
      "confidence": 0.5
    }}
  ],
  "panel_notes": "Any general observations about the panel layout, wire bundles, etc."
}}

IMPORTANT:
- Only report what you can SEE. Set confidence < 0.6 for anything uncertain.
- Tag format: Q=breaker, K=contactor/relay, M=motor, F=fuse/overload, S=switch, H=indicator, T=transformer, U=VFD, B=sensor, X=terminal block
- If you can't read a terminal number, omit it. Don't guess.
- Wire colors should use IEC codes: {WIRE_COLOR_CODES}"""

    return system, user


def followup_photo_prompt(
    *,
    tag: str,
    component_type: str,
    known_terminals: dict[str, str],
    gaps: list[str],
) -> tuple[str, str]:
    """Prompt for a close-up / follow-up photo of a specific component.

    Args:
        tag: Component tag (e.g., "K1")
        component_type: Symbol type (e.g., "contactor_3pole")
        known_terminals: Dict of terminal_id → what we already know
        gaps: List of what we still need
    """
    system = (
        "You are an expert industrial electrician analyzing a close-up photograph "
        "of a specific component in a control panel. Extract terminal connections, "
        "wire colors, and nameplate data."
    )

    known_str = "\n".join(
        f"  - Terminal {tid}: {info}" for tid, info in known_terminals.items()
    ) or "  (none yet)"

    gaps_str = "\n".join(f"  - {g}" for g in gaps) or "  (none)"

    user = f"""Analyzing close-up of component {tag} (type: {component_type}).

ALREADY KNOWN:
{known_str}

STILL UNKNOWN:
{gaps_str}

Focus on:
1. Terminal numbers and their wire connections
2. Wire colors at each terminal
3. Nameplate data (manufacturer, part number, ratings)
4. Any wire labels/ferrules visible

RESPOND IN JSON ONLY:
{{
  "tag": "{tag}",
  "terminals_found": [
    {{
      "terminal_id": "A1",
      "connected_to": "S1.4",
      "wire_color": "RD",
      "wire_label": "W5"
    }}
  ],
  "nameplate": {{
    "manufacturer": "",
    "part_number": "",
    "voltage_rating": "",
    "current_rating": ""
  }},
  "notes": "Any observations about this component"
}}"""

    return system, user


def answer_parsing_prompt(
    *,
    tag: str,
    component_type: str,
    question: str,
    answer: str,
) -> tuple[str, str]:
    """Prompt to parse a technician's text answer into structured updates.

    Args:
        tag: Component being discussed
        component_type: Symbol type
        question: What we asked the tech
        answer: What they typed back
    """
    system = (
        "You are a parser that converts a field technician's plain-English answer "
        "about electrical connections into structured JSON data. The technician may "
        "use informal language. Parse precisely."
    )

    user = f"""Parse this technician's answer about component {tag} (type: {component_type}).

WE ASKED: "{question}"
TECH ANSWERED: "{answer}"

Extract any of the following from the answer:
1. Connections: which terminals connect to what
2. Terminal updates: wire colors, labels, gauges
3. Component updates: ratings, part number, manufacturer

RESPOND IN JSON ONLY:
{{
  "connections": [
    {{
      "from": "TAG.TERMINAL",
      "to": "TAG.TERMINAL",
      "wire_type": "power|control|signal|earth|neutral",
      "wire_color": "IEC color code or null",
      "confidence": 0.9
    }}
  ],
  "terminal_updates": [
    {{
      "tag": "{tag}",
      "terminal_id": "...",
      "wire_color": "...",
      "wire_label": "...",
      "wire_gauge": "..."
    }}
  ],
  "component_updates": {{
    "tag": "{tag}",
    "manufacturer": null,
    "part_number": null,
    "voltage_rating": null,
    "current_rating": null
  }},
  "notes": "Anything ambiguous or needing clarification"
}}

Tag reference: Q=breaker, K=contactor/relay, M=motor, F=fuse/overload, S=switch.
Wire color codes: {WIRE_COLOR_CODES}
"all phases" or "all three" means connections on terminals 1→2, 3→4, 5→6.
"load side" = even terminals (2,4,6). "line side" = odd terminals (1,3,5).
"coil" = A1, A2 terminals."""

    return system, user
