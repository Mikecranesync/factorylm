"""Knowledge Base enrichment from field discoveries.

When a component isn't found in the KB, this module creates a new
KB atom from data gathered during reconstruction.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from openclaw.wiring.models import ComponentRecord, WiringProject

log = logging.getLogger(__name__)


def can_create_atom(comp: ComponentRecord) -> bool:
    """Check if we have enough data to create a KB atom for this component."""
    return bool(
        comp.manufacturer
        and comp.part_number
        and comp.component_type
        and len(comp.terminals) >= 2
    )


def build_atom_data(comp: ComponentRecord) -> dict[str, Any]:
    """Build a KB atom dict from a ComponentRecord.

    Returns a dict matching the knowledge_atoms table schema:
        atom_type, vendor, product, content, keywords
    """
    # Build terminal layout description
    terminal_lines = []
    for tid, term in sorted(comp.terminals.items()):
        parts = [f"Terminal {tid}"]
        if term.label:
            parts.append(f"({term.label})")
        if term.connected_to:
            parts.append(f"→ {term.connected_to}")
        if term.wire_color:
            parts.append(f"[{term.wire_color}]")
        terminal_lines.append(" ".join(parts))

    # Build content string
    content_parts = [
        f"Component: {comp.component_type}",
        f"Manufacturer: {comp.manufacturer}",
        f"Part Number: {comp.part_number}",
    ]
    if comp.voltage_rating:
        content_parts.append(f"Voltage Rating: {comp.voltage_rating}")
    if comp.current_rating:
        content_parts.append(f"Current Rating: {comp.current_rating}")
    if comp.description:
        content_parts.append(f"Description: {comp.description}")
    content_parts.append("")
    content_parts.append("Terminal Layout:")
    content_parts.extend(terminal_lines)

    # Build keywords for search
    keywords = list(filter(None, [
        comp.part_number,
        comp.manufacturer,
        comp.component_type,
        comp.description,
    ]))

    return {
        "atom_type": "spec",
        "vendor": comp.manufacturer,
        "product": comp.part_number,
        "content": "\n".join(content_parts),
        "keywords": keywords,
        "terminal_layout": {
            tid: {
                "label": term.label,
                "connected_to": term.connected_to,
            }
            for tid, term in comp.terminals.items()
        },
        "ratings": {
            "voltage": comp.voltage_rating,
            "current": comp.current_rating,
        },
    }


def enrich_from_project(project: WiringProject) -> list[dict[str, Any]]:
    """Find all components without KB atoms and build atom data for them.

    Returns a list of atom dicts ready for insertion.
    """
    atoms = []
    for tag, comp in project.components.items():
        if comp.kb_atom_id is not None:
            continue  # Already linked to KB
        if not can_create_atom(comp):
            continue  # Not enough data yet
        atom = build_atom_data(comp)
        atom["source_tag"] = tag
        atom["source_project"] = project.project_id
        atoms.append(atom)
    return atoms


def insert_atom(atom_data: dict[str, Any]) -> Optional[int]:
    """Insert a KB atom into the knowledge_atoms table.

    Returns the new atom_id if successful, None otherwise.
    """
    try:
        from openclaw.connectors.knowledge import KnowledgeConnector
        kb = KnowledgeConnector()
        atom_id = kb.insert_atom(
            atom_type=atom_data["atom_type"],
            vendor=atom_data["vendor"],
            product=atom_data["product"],
            content=atom_data["content"],
            keywords=atom_data["keywords"],
        )
        log.info("Created KB atom %d for %s %s", atom_id, atom_data["vendor"], atom_data["product"])
        return atom_id
    except ImportError:
        log.warning("KnowledgeConnector not available — KB enrichment requires VPS deployment")
        return None
    except Exception as e:
        log.error("Failed to insert KB atom: %s", e)
        return None
