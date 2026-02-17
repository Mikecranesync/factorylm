"""Six-stage wiring reconstruction pipeline.

    Photo arrives
        │
        ▼
    [INGEST]       ─── Hash photo, add to project.photos
        │
        ▼
    [TAG_IDENTIFY] ─── Vision LLM extracts tags, types, connections
        │
        ▼
    [KB_LOOKUP]    ─── Search KB for terminal layouts + specs
        │
        ▼
    [MODEL_UPDATE] ─── Merge vision + KB data into WiringProject
        │
        ▼
    [GAP_ANALYSIS] ─── Compute unknowns, rank by priority
        │
        ▼
    [DECIDE]       ─── Build diagram (>=80%) or generate next question
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

from openclaw.diagram.renderer import WiringRenderer
from openclaw.diagram.schema import (
    Bus,
    Component,
    Connection,
    DiagramSpec,
    Ratings,
    Terminal,
)
from openclaw.diagram.symbols import SYMBOL_REGISTRY
from openclaw.wiring.gaps import find_gaps, generate_next_question, suggest_continuity_test
from openclaw.wiring.models import (
    ComponentRecord,
    PhotoEvidence,
    TerminalState,
    WiringConnection,
    WiringProject,
)
from openclaw.wiring.prompts import (
    answer_parsing_prompt,
    followup_photo_prompt,
    initial_photo_prompt,
)

log = logging.getLogger(__name__)

# Completeness threshold for auto-generating diagram
COMPLETENESS_THRESHOLD = 80.0


@dataclass
class PipelineResult:
    """Result from running the pipeline on a photo or answer."""

    project: WiringProject
    components_found: int = 0
    connections_found: int = 0
    kb_matches: int = 0
    completeness: float = 0.0
    next_question: Optional[str] = None
    continuity_suggestion: Optional[str] = None
    diagram_ready: bool = False
    summary: str = ""


# ---------------------------------------------------------------------------
# Stage 1: INGEST — hash and register the photo
# ---------------------------------------------------------------------------

def _ingest_photo(project: WiringProject, photo_path: str) -> PhotoEvidence:
    """Hash the photo file and add it to the project's photo list."""
    path = Path(photo_path)
    if not path.exists():
        raise FileNotFoundError(f"Photo not found: {photo_path}")

    # SHA-256 hash, truncated to 16 chars
    file_bytes = path.read_bytes()
    photo_hash = hashlib.sha256(file_bytes).hexdigest()[:16]

    # Check for duplicate
    for existing in project.photos:
        if existing.photo_id == photo_hash:
            log.info("Photo already ingested: %s", photo_hash)
            return existing

    evidence = PhotoEvidence(
        photo_id=photo_hash,
        timestamp=datetime.now().isoformat(),
        file_path=str(path.resolve()),
    )
    project.photos.append(evidence)
    log.info("Ingested photo %s from %s", photo_hash, photo_path)
    return evidence


def _photo_to_base64(photo_path: str) -> str:
    """Read a photo file and return base64-encoded string."""
    return base64.b64encode(Path(photo_path).read_bytes()).decode("utf-8")


# ---------------------------------------------------------------------------
# Stage 2: TAG_IDENTIFY — call vision LLM
# ---------------------------------------------------------------------------

def _call_vision_llm(
    photo_path: str,
    system_prompt: str,
    user_prompt: str,
) -> dict[str, Any]:
    """Call a vision LLM with a photo and structured prompt.

    Tries Gemini 2.0 Flash first (already integrated), falls back to
    a mock response for offline/testing use.
    """
    photo_b64 = _photo_to_base64(photo_path)
    mime_type = _guess_mime(photo_path)

    # Try Google Gemini (primary vision LLM)
    try:
        return _call_gemini(photo_b64, mime_type, system_prompt, user_prompt)
    except Exception as e:
        log.warning("Gemini call failed: %s — trying Anthropic", e)

    # Try Anthropic Claude (fallback)
    try:
        return _call_claude(photo_b64, mime_type, system_prompt, user_prompt)
    except Exception as e:
        log.warning("Claude call failed: %s — returning empty result", e)

    return {"components": [], "connections": [], "panel_notes": "Vision LLM unavailable"}


def _guess_mime(path: str) -> str:
    """Guess MIME type from file extension."""
    ext = Path(path).suffix.lower()
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }.get(ext, "image/jpeg")


def _call_gemini(
    photo_b64: str,
    mime_type: str,
    system_prompt: str,
    user_prompt: str,
) -> dict[str, Any]:
    """Call Google Gemini 2.0 Flash for vision analysis."""
    import google.generativeai as genai  # type: ignore
    import os

    api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY or GEMINI_API_KEY not set")

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        "gemini-2.0-flash",
        system_instruction=system_prompt,
    )

    image_bytes = base64.b64decode(photo_b64)
    response = model.generate_content(
        [
            {"mime_type": mime_type, "data": image_bytes},
            user_prompt,
        ],
        generation_config={"response_mime_type": "application/json"},
    )

    return json.loads(response.text)


def _call_claude(
    photo_b64: str,
    mime_type: str,
    system_prompt: str,
    user_prompt: str,
) -> dict[str, Any]:
    """Call Anthropic Claude for vision analysis."""
    import anthropic
    import os

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")

    client = anthropic.Anthropic(api_key=api_key)

    # Map mime types for Claude
    media_type = mime_type
    if media_type == "image/jpg":
        media_type = "image/jpeg"

    response = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=4096,
        system=system_prompt,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": photo_b64,
                        },
                    },
                    {"type": "text", "text": user_prompt},
                ],
            }
        ],
    )

    # Parse JSON from response
    text = response.content[0].text
    # Strip markdown code fences if present
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        if text.endswith("```"):
            text = text[:-3]
    return json.loads(text)


def _call_text_llm(system_prompt: str, user_prompt: str) -> dict[str, Any]:
    """Call a text LLM (no image) for answer parsing."""
    # Try Anthropic first
    try:
        import anthropic
        import os

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if api_key:
            client = anthropic.Anthropic(api_key=api_key)
            response = client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=2048,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            text = response.content[0].text
            if text.startswith("```"):
                text = text.split("\n", 1)[1]
                if text.endswith("```"):
                    text = text[:-3]
            return json.loads(text)
    except Exception as e:
        log.warning("Text LLM call failed: %s", e)

    return {"connections": [], "terminal_updates": [], "component_updates": {}, "notes": ""}


# ---------------------------------------------------------------------------
# Stage 3: KB_LOOKUP — search knowledge base for terminal layouts
# ---------------------------------------------------------------------------

def _kb_lookup(comp: ComponentRecord) -> Optional[dict]:
    """Search the KB for terminal layout and specs for a component.

    Uses KnowledgeConnector with two strategies:
    1. Exact match by vendor + part_number (highest confidence)
    2. Full-text search as fallback
    3. SYMBOL_REGISTRY as last resort (terminal IDs only)

    Returns a dict with terminal_layout, ratings, wiring_model, etc. if found.
    """
    if not comp.part_number and not comp.manufacturer:
        # Still try SYMBOL_REGISTRY
        return _symbol_registry_fallback(comp)

    try:
        from openclaw.connectors.knowledge import KnowledgeConnector

        kb = KnowledgeConnector()

        # Strategy 1: exact part lookup
        if comp.manufacturer and comp.part_number:
            exact = kb.find_by_part(comp.manufacturer, comp.part_number)
            if exact:
                exact["source"] = "knowledge_atoms_exact"
                return exact

        # Strategy 2: full-text search
        search_terms = " ".join(filter(None, [
            comp.part_number,
            comp.manufacturer,
            comp.component_type,
            "terminal wiring",
        ]))
        results = kb.search(search_terms, vendor=comp.manufacturer)
        if results:
            results[0]["source"] = "knowledge_atoms_search"
            return results[0]

    except ImportError:
        log.debug("KnowledgeConnector not available, using SYMBOL_REGISTRY fallback")
    except Exception as e:
        log.debug("KB search failed: %s", e)

    return _symbol_registry_fallback(comp)


def _symbol_registry_fallback(comp: ComponentRecord) -> Optional[dict]:
    """Use SYMBOL_REGISTRY for terminal IDs when KB is unavailable."""
    if comp.component_type and comp.component_type in SYMBOL_REGISTRY:
        draw_fn = SYMBOL_REGISTRY[comp.component_type]
        try:
            _, terminal_map = draw_fn(0, 0, tag="X")
            return {
                "source": "SYMBOL_REGISTRY",
                "terminal_ids": list(terminal_map.keys()),
            }
        except Exception:
            pass
    return None


# ---------------------------------------------------------------------------
# Stage 4: MODEL_UPDATE — merge vision + KB into project
# ---------------------------------------------------------------------------

def _merge_vision_results(
    project: WiringProject,
    vision_data: dict[str, Any],
    evidence: PhotoEvidence,
) -> tuple[int, int]:
    """Merge vision LLM results into the project model.

    Returns (components_added_or_updated, connections_added).
    """
    comp_count = 0
    conn_count = 0

    # Process components
    for raw_comp in vision_data.get("components", []):
        tag = raw_comp.get("tag", "").upper()
        if not tag:
            continue

        confidence = float(raw_comp.get("confidence", 0.5))
        comp = project.add_or_update_component(
            tag,
            component_type=raw_comp.get("type", ""),
            manufacturer=raw_comp.get("manufacturer", ""),
            part_number=raw_comp.get("part_number", ""),
            mounting_location=raw_comp.get("mounting_location", ""),
            confidence=confidence,
        )
        comp.evidence.append(evidence)

        # Add discovered terminals
        for tid in raw_comp.get("visible_terminals", []):
            if tid not in comp.terminals:
                comp.terminals[tid] = TerminalState(
                    terminal_id=tid,
                    evidence=[evidence],
                )

        comp_count += 1

    # Process connections
    for raw_conn in vision_data.get("connections", []):
        from_ref = raw_conn.get("from", "")
        to_ref = raw_conn.get("to", "")
        if not from_ref or not to_ref:
            continue

        confidence = float(raw_conn.get("confidence", 0.4))
        project.add_connection(
            from_ref=from_ref.upper(),
            to_ref=to_ref.upper(),
            wire_color=raw_conn.get("wire_color"),
            wire_label=raw_conn.get("wire_label"),
            confidence=confidence,
            evidence=[evidence],
        )
        conn_count += 1

    # Store panel notes
    notes = vision_data.get("panel_notes", "")
    if notes:
        project.notes.append(notes)

    return comp_count, conn_count


def _merge_kb_data(comp: ComponentRecord, kb_data: dict) -> bool:
    """Merge KB lookup results into a component record.

    Returns True if KB data was applied.
    """
    if not kb_data:
        return False

    source = kb_data.get("source", "")

    if source == "SYMBOL_REGISTRY":
        # Just add terminal stubs for expected terminals
        for tid in kb_data.get("terminal_ids", []):
            if tid not in comp.terminals:
                comp.terminals[tid] = TerminalState(terminal_id=tid)
        return True

    # Full KB match — higher confidence
    if "terminal_layout" in kb_data:
        for tid, info in kb_data["terminal_layout"].items():
            if tid not in comp.terminals:
                comp.terminals[tid] = TerminalState(
                    terminal_id=tid,
                    label=info.get("label", ""),
                )
            else:
                term = comp.terminals[tid]
                if not term.label and info.get("label"):
                    term.label = info["label"]

    if "ratings" in kb_data:
        ratings = kb_data["ratings"]
        if not comp.voltage_rating and ratings.get("voltage"):
            comp.voltage_rating = ratings["voltage"]
        if not comp.current_rating and ratings.get("current"):
            comp.current_rating = ratings["current"]

    comp.confidence = max(comp.confidence, 0.9)
    return True


# ---------------------------------------------------------------------------
# Stage 5+6: GAP_ANALYSIS + DECIDE — via gaps.py
# ---------------------------------------------------------------------------


def process_photo(
    project: WiringProject,
    photo_path: str,
    focus_tag: Optional[str] = None,
) -> PipelineResult:
    """Run the full 6-stage pipeline on a photo.

    Args:
        project: The wiring project to update.
        photo_path: Path to the photo file.
        focus_tag: If set, focus vision analysis on this component.

    Returns:
        PipelineResult with updated project and next steps.
    """
    # Stage 1: INGEST
    evidence = _ingest_photo(project, photo_path)

    # Stage 2: TAG_IDENTIFY
    if focus_tag and focus_tag in project.components:
        # Follow-up photo for a specific component
        comp = project.components[focus_tag]
        known = {}
        gaps_list = []
        for tid, term in comp.terminals.items():
            if term.connected_to:
                known[tid] = f"→ {term.connected_to}"
                if term.wire_color:
                    known[tid] += f" ({term.wire_color})"
            else:
                gaps_list.append(f"Terminal {tid} connection unknown")

        system, user = followup_photo_prompt(
            tag=focus_tag,
            component_type=comp.component_type,
            known_terminals=known,
            gaps=gaps_list,
        )
    else:
        # Initial panel photo
        system, user = initial_photo_prompt(focus_tag=focus_tag)

    vision_data = _call_vision_llm(photo_path, system, user)

    # Stage 3: KB_LOOKUP (for each discovered component)
    kb_matches = 0
    # First merge vision data to populate component records
    comp_count, conn_count = _merge_vision_results(project, vision_data, evidence)

    # Then do KB lookups for all components
    for tag, comp in project.components.items():
        kb_data = _kb_lookup(comp)
        if _merge_kb_data(comp, kb_data):
            kb_matches += 1

    # Stage 4: MODEL_UPDATE — already done in merge steps above

    # Stage 5+6: GAP_ANALYSIS + DECIDE
    completeness = project.completeness()
    gaps = find_gaps(project)
    next_q = generate_next_question(project)
    cont_suggest = suggest_continuity_test(project)
    diagram_ready = completeness >= COMPLETENESS_THRESHOLD

    # Build summary
    summary_parts = [
        f"Components: {comp_count} found ({len(project.components)} total)",
        f"Connections: {conn_count} new ({len(project.connections)} total)",
        f"KB matches: {kb_matches}",
        f"Completeness: {completeness:.0f}%",
    ]
    if diagram_ready:
        summary_parts.append("DIAGRAM READY — run 'wd build-diagram'")
    elif next_q:
        summary_parts.append(f"Next: {next_q}")

    return PipelineResult(
        project=project,
        components_found=comp_count,
        connections_found=conn_count,
        kb_matches=kb_matches,
        completeness=completeness,
        next_question=next_q,
        continuity_suggestion=cont_suggest,
        diagram_ready=diagram_ready,
        summary="\n".join(summary_parts),
    )


def process_answer(
    project: WiringProject,
    answer_text: str,
) -> PipelineResult:
    """Process a technician's text answer through the pipeline.

    Parses the answer via LLM and merges structured data into the project.
    """
    tag = project.current_focus_tag or ""
    comp = project.components.get(tag)
    comp_type = comp.component_type if comp else ""
    question = project.pending_question or "general question about the panel"

    system, user = answer_parsing_prompt(
        tag=tag,
        component_type=comp_type,
        question=question,
        answer=answer_text,
    )

    parsed = _call_text_llm(system, user)

    # Apply connections
    conn_count = 0
    for raw_conn in parsed.get("connections", []):
        from_ref = raw_conn.get("from", "")
        to_ref = raw_conn.get("to", "")
        if from_ref and to_ref:
            project.add_connection(
                from_ref=from_ref.upper(),
                to_ref=to_ref.upper(),
                wire_type=raw_conn.get("wire_type", "power"),
                wire_color=raw_conn.get("wire_color"),
                confidence=float(raw_conn.get("confidence", 0.8)),
            )
            conn_count += 1

    # Apply terminal updates
    for update in parsed.get("terminal_updates", []):
        utag = update.get("tag", tag).upper()
        tid = update.get("terminal_id", "")
        ucomp = project.components.get(utag)
        if ucomp and tid:
            if tid not in ucomp.terminals:
                ucomp.terminals[tid] = TerminalState(terminal_id=tid)
            term = ucomp.terminals[tid]
            if update.get("wire_color"):
                term.wire_color = update["wire_color"]
            if update.get("wire_label"):
                term.wire_label = update["wire_label"]
            if update.get("wire_gauge"):
                term.wire_gauge = update["wire_gauge"]

    # Apply component updates
    comp_updates = parsed.get("component_updates", {})
    if comp_updates and comp_updates.get("tag"):
        utag = comp_updates["tag"].upper()
        if utag in project.components:
            ucomp = project.components[utag]
            for field in ("manufacturer", "part_number", "voltage_rating", "current_rating"):
                val = comp_updates.get(field)
                if val:
                    setattr(ucomp, field, val)

    # Notes
    notes = parsed.get("notes", "")
    if notes:
        project.notes.append(f"[answer] {notes}")

    # Clear pending question
    project.pending_question = None

    # Recompute gaps
    completeness = project.completeness()
    next_q = generate_next_question(project)
    diagram_ready = completeness >= COMPLETENESS_THRESHOLD

    if next_q:
        project.pending_question = next_q

    return PipelineResult(
        project=project,
        connections_found=conn_count,
        completeness=completeness,
        next_question=next_q,
        diagram_ready=diagram_ready,
        summary=f"Parsed answer: {conn_count} connections added. Completeness: {completeness:.0f}%",
    )


# ---------------------------------------------------------------------------
# Diagram generation: WiringProject → DiagramSpec → PNG
# ---------------------------------------------------------------------------

def build_diagram_spec(project: WiringProject) -> DiagramSpec:
    """Convert a WiringProject into a DiagramSpec for rendering."""
    components: list[Component] = []
    connections: list[Connection] = []
    buses: list[Bus] = []

    for tag, comp in project.components.items():
        if not comp.component_type:
            continue
        if comp.component_type not in SYMBOL_REGISTRY:
            log.warning("Skipping %s: unknown type %s", tag, comp.component_type)
            continue

        terminals = [
            Terminal(id=tid, label=term.label, side="top")
            for tid, term in comp.terminals.items()
        ]

        ratings = None
        if comp.voltage_rating or comp.current_rating:
            ratings = Ratings(
                voltage=comp.voltage_rating,
                current=comp.current_rating,
            )

        components.append(Component(
            tag=tag,
            type=comp.component_type,
            label=comp.description or f"{comp.manufacturer} {comp.part_number}".strip(),
            ratings=ratings,
            terminals=terminals,
            group=comp.group,
        ))

    for conn in project.connections:
        wire_type = conn.wire_type or "power"
        connections.append(Connection(
            **{
                "from": conn.from_ref,
                "to": conn.to_ref,
            },
            wire_label=conn.wire_label or "",
            wire_type=wire_type,
            gauge=conn.wire_gauge,
        ))

    for bus in project.buses:
        buses.append(Bus(
            name=bus.name,
            type=bus.bus_type,
        ))

    project.revision += 1

    return DiagramSpec(
        title=f"{project.panel_name} — Reconstructed Wiring Diagram",
        drawing_number=f"FLM-WD-{project.project_id[:6].upper()}",
        revision=str(project.revision),
        author="Jarvis (Wiring Reconstruction)",
        date=date.today().isoformat(),
        standard=project.standard.value,
        description=f"Reconstructed from {len(project.photos)} photos, {len(project.connections)} connections",
        notes=project.notes[:5],
        components=components,
        connections=connections,
        buses=buses,
    )


def render_diagram(project: WiringProject, output_path: str, hires: bool = False) -> str:
    """Build and render a diagram from the project. Returns the output path."""
    spec = build_diagram_spec(project)
    renderer = WiringRenderer(spec)
    renderer.render_png_to_file(output_path, hires=hires)
    return output_path
