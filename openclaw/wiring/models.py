"""Pydantic models for the wiring reconstruction project.

A WiringProject is the persistent state that grows as photos arrive.
It tracks components, terminals, connections, and evidence — keyed by
component tags (Q1, K1, M1, etc.).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Standard(str, Enum):
    IEC = "IEC"
    ANSI = "ANSI"


class PhotoEvidence(BaseModel):
    """A reference to a photo used as evidence for a discovery."""

    photo_id: str = Field(..., description="SHA-256[:16] of the image file")
    timestamp: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
    )
    region_description: str = Field(default="", description="What part of the panel this photo covers")
    file_path: str = Field(default="", description="Local path to the photo file")


class TerminalState(BaseModel):
    """State of a single terminal on a component."""

    terminal_id: str = Field(..., description="Terminal number/name (e.g., '1', 'A1', 'U1')")
    label: str = Field(default="", description="Functional label (e.g., 'Line', 'Load')")
    connected_to: Optional[str] = Field(
        default=None,
        description="What this terminal connects to, as 'TAG.TERMINAL' (e.g., 'K1.A1')",
    )
    wire_color: Optional[str] = Field(
        default=None,
        description="IEC wire color code (BK/BU/BN/GN-YE/RD/WH/GY)",
    )
    wire_label: Optional[str] = Field(default=None, description="Wire number/label")
    wire_gauge: Optional[str] = Field(default=None, description="Wire gauge (e.g., '2.5mm²')")
    confirmed: bool = Field(default=False, description="Tech-confirmed via test or explicit answer")
    evidence: list[PhotoEvidence] = Field(default_factory=list)


class ComponentRecord(BaseModel):
    """A single component discovered during reconstruction."""

    tag: str = Field(..., description="Device designation (Q1, K1, M1, etc.)")
    component_type: str = Field(
        default="",
        description="Type key matching SYMBOL_REGISTRY (e.g., 'contactor_3pole')",
    )
    manufacturer: str = Field(default="")
    part_number: str = Field(default="")
    description: str = Field(default="")
    voltage_rating: Optional[str] = Field(default=None)
    current_rating: Optional[str] = Field(default=None)
    kb_atom_id: Optional[int] = Field(
        default=None,
        description="Link to knowledge_atoms table entry",
    )
    terminals: dict[str, TerminalState] = Field(
        default_factory=dict,
        description="Map of terminal_id → TerminalState",
    )
    mounting_location: str = Field(default="", description="Physical location in panel")
    group: str = Field(default="main", description="Logical group for diagram layout")
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Overall component confidence (0.0–1.0)",
    )
    evidence: list[PhotoEvidence] = Field(default_factory=list)


class WiringConnection(BaseModel):
    """A wire connection between two terminal references."""

    from_ref: str = Field(..., description="Source terminal as 'TAG.TERMINAL'")
    to_ref: str = Field(..., description="Destination terminal as 'TAG.TERMINAL'")
    wire_type: str = Field(default="power", description="power, control, signal, earth, neutral")
    wire_color: Optional[str] = Field(default=None, description="IEC color code")
    wire_label: Optional[str] = Field(default=None)
    wire_gauge: Optional[str] = Field(default=None)
    confirmed: bool = Field(default=False)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence: list[PhotoEvidence] = Field(default_factory=list)


class ProjectBus(BaseModel):
    """A power rail or bus bar in the project."""

    name: str = Field(..., description="Bus label (L1, L2, L3, PE, +24V, 0V, N)")
    bus_type: str = Field(default="power", description="power, control, earth, neutral")
    confirmed: bool = Field(default=False)


class WiringProject(BaseModel):
    """Persistent project state that grows as photos and answers arrive."""

    project_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    panel_name: str = Field(default="Unnamed Panel")
    panel_location: str = Field(default="")
    standard: Standard = Field(default=Standard.IEC)
    revision: int = Field(default=0)

    components: dict[str, ComponentRecord] = Field(
        default_factory=dict,
        description="Map of tag → ComponentRecord",
    )
    connections: list[WiringConnection] = Field(default_factory=list)
    buses: list[ProjectBus] = Field(default_factory=list)
    photos: list[PhotoEvidence] = Field(default_factory=list)

    current_focus_tag: Optional[str] = Field(
        default=None,
        description="Which component we're currently asking about",
    )
    pending_question: Optional[str] = Field(default=None)
    notes: list[str] = Field(default_factory=list)

    # -- Computed helpers (not persisted, re-derived) --

    def completeness(self) -> float:
        """Compute overall project completeness as a percentage.

        Counts known fields across all components and connections.
        """
        if not self.components:
            return 0.0

        total_fields = 0
        known_fields = 0

        for comp in self.components.values():
            # Core component fields: type, manufacturer, part_number
            total_fields += 3
            if comp.component_type:
                known_fields += 1
            if comp.manufacturer:
                known_fields += 1
            if comp.part_number:
                known_fields += 1

            # Terminal fields: each terminal has connected_to, wire_color
            for term in comp.terminals.values():
                total_fields += 2
                if term.connected_to:
                    known_fields += 1
                if term.wire_color:
                    known_fields += 1

        if total_fields == 0:
            return 0.0

        return round((known_fields / total_fields) * 100, 1)

    def get_component(self, tag: str) -> Optional[ComponentRecord]:
        """Get a component by tag, case-insensitive."""
        return self.components.get(tag) or self.components.get(tag.upper())

    def add_or_update_component(self, tag: str, **kwargs) -> ComponentRecord:
        """Add a new component or update an existing one.

        Higher-confidence values win on conflicts.
        """
        tag = tag.upper()
        if tag in self.components:
            comp = self.components[tag]
            new_conf = kwargs.get("confidence", 0.0)
            for key, value in kwargs.items():
                if value is None:
                    continue
                if key == "confidence":
                    comp.confidence = max(comp.confidence, value)
                    continue
                current = getattr(comp, key, None)
                # Only overwrite if new confidence >= existing
                if not current or new_conf >= comp.confidence:
                    setattr(comp, key, value)
        else:
            self.components[tag] = ComponentRecord(tag=tag, **kwargs)
        return self.components[tag]

    def add_connection(
        self,
        from_ref: str,
        to_ref: str,
        *,
        wire_type: str = "power",
        wire_color: Optional[str] = None,
        wire_label: Optional[str] = None,
        confidence: float = 0.5,
        confirmed: bool = False,
        evidence: Optional[list[PhotoEvidence]] = None,
    ) -> WiringConnection:
        """Add a connection, avoiding duplicates."""
        # Check for existing connection
        for conn in self.connections:
            if (conn.from_ref == from_ref and conn.to_ref == to_ref) or (
                conn.from_ref == to_ref and conn.to_ref == from_ref
            ):
                # Update if higher confidence
                if confidence > conn.confidence:
                    conn.wire_type = wire_type
                    conn.wire_color = wire_color or conn.wire_color
                    conn.wire_label = wire_label or conn.wire_label
                    conn.confidence = confidence
                    conn.confirmed = confirmed or conn.confirmed
                if evidence:
                    conn.evidence.extend(evidence)
                return conn

        conn = WiringConnection(
            from_ref=from_ref,
            to_ref=to_ref,
            wire_type=wire_type,
            wire_color=wire_color,
            wire_label=wire_label,
            confidence=confidence,
            confirmed=confirmed,
            evidence=evidence or [],
        )
        self.connections.append(conn)

        # Also update terminal states on the components
        self._update_terminal_connection(from_ref, to_ref, wire_color, wire_label, confidence, confirmed)
        self._update_terminal_connection(to_ref, from_ref, wire_color, wire_label, confidence, confirmed)

        return conn

    def _update_terminal_connection(
        self,
        ref: str,
        connected_to: str,
        wire_color: Optional[str],
        wire_label: Optional[str],
        confidence: float,
        confirmed: bool,
    ) -> None:
        """Update a terminal's connected_to field from a connection."""
        parts = ref.split(".", 1)
        if len(parts) != 2:
            return
        tag, terminal_id = parts
        comp = self.components.get(tag)
        if not comp:
            return
        if terminal_id not in comp.terminals:
            comp.terminals[terminal_id] = TerminalState(terminal_id=terminal_id)
        term = comp.terminals[terminal_id]
        if confidence >= (0.9 if term.confirmed else 0.0):
            term.connected_to = connected_to
            if wire_color:
                term.wire_color = wire_color
            if wire_label:
                term.wire_label = wire_label
            if confirmed:
                term.confirmed = True

    def remove_connection(self, from_ref: str, to_ref: str) -> bool:
        """Remove a connection (e.g., after a failed continuity test)."""
        for i, conn in enumerate(self.connections):
            if (conn.from_ref == from_ref and conn.to_ref == to_ref) or (
                conn.from_ref == to_ref and conn.to_ref == from_ref
            ):
                self.connections.pop(i)
                return True
        return False
