"""Gap analysis for wiring reconstruction projects.

Computes what's unknown, ranks gaps by priority, and generates the
next question to ask the technician.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from openclaw.diagram.symbols import SYMBOL_REGISTRY
from openclaw.wiring.models import ComponentRecord, WiringProject


@dataclass
class Gap:
    """A single piece of missing information."""

    tag: str
    gap_type: str  # "unknown_type", "missing_part_number", "no_terminal_layout", etc.
    priority: int  # Higher = ask first
    description: str
    terminal_id: Optional[str] = None


# Priority levels for gap types (higher = ask first)
GAP_PRIORITIES = {
    "unknown_type": 10,
    "missing_part_number": 8,
    "no_terminal_layout": 7,
    "unknown_power_connection": 5,
    "unknown_control_connection": 3,
    "wire_label_missing": 1,
}


def _expected_terminals(component_type: str) -> list[str]:
    """Get the expected terminal IDs for a component type from the symbol registry.

    Calls the symbol drawing function at (0,0) to discover terminal positions.
    """
    draw_fn = SYMBOL_REGISTRY.get(component_type)
    if not draw_fn:
        return []
    try:
        _, terminals = draw_fn(0, 0, tag="X")
        return list(terminals.keys())
    except Exception:
        return []


def find_gaps(project: WiringProject) -> list[Gap]:
    """Scan the project and find all missing information.

    Returns gaps sorted by priority (highest first).
    """
    gaps: list[Gap] = []

    for tag, comp in project.components.items():
        gaps.extend(_component_gaps(tag, comp))

    gaps.sort(key=lambda g: (-g.priority, g.tag))
    return gaps


def _component_gaps(tag: str, comp: ComponentRecord) -> list[Gap]:
    """Find gaps for a single component."""
    gaps: list[Gap] = []

    # Unknown component type
    if not comp.component_type:
        gaps.append(Gap(
            tag=tag,
            gap_type="unknown_type",
            priority=GAP_PRIORITIES["unknown_type"],
            description=f"Component type unknown for {tag}",
        ))
        return gaps  # Can't check terminals without knowing the type

    # Missing part number (needed for KB lookup)
    if not comp.part_number:
        gaps.append(Gap(
            tag=tag,
            gap_type="missing_part_number",
            priority=GAP_PRIORITIES["missing_part_number"],
            description=f"No part number for {tag} ({comp.component_type})",
        ))

    # Check terminal coverage
    expected = _expected_terminals(comp.component_type)
    if expected and not comp.terminals:
        gaps.append(Gap(
            tag=tag,
            gap_type="no_terminal_layout",
            priority=GAP_PRIORITIES["no_terminal_layout"],
            description=f"No terminal data for {tag} (expected: {', '.join(expected)})",
        ))
    elif expected:
        # Check each expected terminal
        power_terminals = {"1", "2", "3", "4", "5", "6", "R", "S", "T", "U", "V", "W", "U1", "V1", "W1", "L", "N"}
        for tid in expected:
            term = comp.terminals.get(tid)
            if term and term.connected_to:
                continue  # This terminal is known
            is_power = tid in power_terminals
            gap_type = "unknown_power_connection" if is_power else "unknown_control_connection"
            gaps.append(Gap(
                tag=tag,
                gap_type=gap_type,
                priority=GAP_PRIORITIES[gap_type],
                terminal_id=tid,
                description=f"Unknown connection at {tag}.{tid}",
            ))

        # Check for missing wire labels on known connections
        for tid, term in comp.terminals.items():
            if term.connected_to and not term.wire_color:
                gaps.append(Gap(
                    tag=tag,
                    gap_type="wire_label_missing",
                    priority=GAP_PRIORITIES["wire_label_missing"],
                    terminal_id=tid,
                    description=f"Wire color unknown at {tag}.{tid}",
                ))

    return gaps


def generate_next_question(project: WiringProject) -> Optional[str]:
    """Generate the single best next question to ask the technician.

    Groups gaps for the same tag so we don't ask 6 separate questions
    about one component.
    """
    gaps = find_gaps(project)
    if not gaps:
        return None

    # Group gaps by tag, take the highest-priority tag
    tag_gaps: dict[str, list[Gap]] = {}
    for gap in gaps:
        tag_gaps.setdefault(gap.tag, []).append(gap)

    # Pick the tag with the highest-priority gap
    best_tag = max(tag_gaps, key=lambda t: max(g.priority for g in tag_gaps[t]))
    best_gaps = tag_gaps[best_tag]
    top_gap = best_gaps[0]

    # Generate question based on gap type
    comp = project.components.get(best_tag)
    comp_desc = f" ({comp.component_type})" if comp and comp.component_type else ""

    if top_gap.gap_type == "unknown_type":
        return (
            f"I can't identify the component at position '{best_tag}'. "
            f"Can you take a close-up photo of it, including any nameplate or labels?"
        )

    if top_gap.gap_type == "missing_part_number":
        return (
            f"Take a photo of {best_tag}'s{comp_desc} nameplate/data plate "
            f"so I can look up its terminal layout."
        )

    if top_gap.gap_type == "no_terminal_layout":
        expected = _expected_terminals(comp.component_type) if comp else []
        return (
            f"I need to see {best_tag}'s{comp_desc} terminal block. "
            f"Take a close-up showing the terminal numbers "
            f"(expecting: {', '.join(expected)})."
        )

    if top_gap.gap_type == "unknown_power_connection":
        # Group power terminal gaps for this component
        power_gaps = [g for g in best_gaps if g.gap_type == "unknown_power_connection"]
        terminals = [g.terminal_id for g in power_gaps if g.terminal_id]
        if _are_load_side(terminals):
            return (
                f"Take a close-up of {best_tag}'s{comp_desc} load-side terminals "
                f"({', '.join(terminals)}) showing the wires."
            )
        if _are_line_side(terminals):
            return (
                f"Take a close-up of {best_tag}'s{comp_desc} line-side terminals "
                f"({', '.join(terminals)}) showing the wires."
            )
        return (
            f"Take a close-up of {best_tag}'s{comp_desc} "
            f"terminals {', '.join(terminals)} showing the wire connections."
        )

    if top_gap.gap_type == "unknown_control_connection":
        ctrl_gaps = [g for g in best_gaps if g.gap_type == "unknown_control_connection"]
        terminals = [g.terminal_id for g in ctrl_gaps if g.terminal_id]
        if len(terminals) == 1:
            return f"Where does the wire from {best_tag}.{terminals[0]} go?"
        return (
            f"I need to trace the control wiring on {best_tag}{comp_desc}. "
            f"Can you check terminals {', '.join(terminals)}?"
        )

    if top_gap.gap_type == "wire_label_missing":
        return (
            f"Can you read the ferrule or identify the wire color "
            f"on {best_tag}.{top_gap.terminal_id}?"
        )

    return f"I need more information about {best_tag}{comp_desc}."


def suggest_continuity_test(project: WiringProject) -> Optional[str]:
    """When photos can't resolve a connection, suggest a continuity test.

    Looks for low-confidence connections that could be confirmed.
    """
    for conn in project.connections:
        if not conn.confirmed and conn.confidence < 0.7:
            return (
                f"I'm not sure about the connection {conn.from_ref} → {conn.to_ref} "
                f"(confidence: {conn.confidence:.0%}). Can you check continuity "
                f"between {conn.from_ref} and {conn.to_ref}?"
            )
    return None


def _are_load_side(terminals: list[str]) -> bool:
    """Check if all terminals are load-side (even numbers: 2, 4, 6)."""
    return all(t in {"2", "4", "6"} for t in terminals) and len(terminals) > 1


def _are_line_side(terminals: list[str]) -> bool:
    """Check if all terminals are line-side (odd numbers: 1, 3, 5)."""
    return all(t in {"1", "3", "5"} for t in terminals) and len(terminals) > 1
