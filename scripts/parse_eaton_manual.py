#!/usr/bin/env python3
"""Parse the Eaton Wiring Manual PDF into structured KB atoms.

Reads the Eaton Wiring Manual (PU08703001Z) and produces a JSON file
of knowledge atoms ready for loading into the rivet PostgreSQL KB.

Usage:
    python scripts/parse_eaton_manual.py [--pdf PATH] [--output PATH]

Defaults:
    --pdf     ~/Downloads/eaton-wiring-manual-pu08703001z-en-en-us.pdf
    --output  eaton_atoms.json
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    print("PyMuPDF required: pip install pymupdf", file=sys.stderr)
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Chapter boundaries from the Eaton manual TOC
# ---------------------------------------------------------------------------
CHAPTERS = [
    (3, 18, "Introduction", "intro"),
    (19, 74, "Pilot devices", "pilot_devices"),
    (75, 180, "Switching, control, visualization", "switching_control"),
    (181, 238, "Motors", "motors"),
    (239, 284, "Contactors and motor-protective circuit-breakers/relays", "contactors"),
    (285, 394, "Electronic motor starter and variable frequency drives", "vfd"),
    (395, 410, "Cam switches", "cam_switches"),
    (411, 436, "Circuit-breakers", "circuit_breakers"),
    (437, 456, "Power distribution equipment", "power_distribution"),
    (457, 502, "Export to World Markets and North America", "export"),
    (503, 574, "Standards, formulae, tables", "standards"),
    (575, 594, "Index", "index"),
]

# Atom type classification patterns
PROCEDURE_PATTERNS = [
    r"wiring\s+(diagram|sequence|instruction)",
    r"connection\s+(diagram|sequence)",
    r"step\s+\d",
    r"(connect|wire)\s+.+\s+to\s+",
    r"terminal\s+(assignment|designation|layout)",
]

FAULT_PATTERNS = [
    r"fault\s+(code|detection|indication)",
    r"error\s+(code|message)",
    r"trip\s+(class|curve|setting)",
    r"overload\s+(protection|relay|setting)",
    r"short[\s-]circuit",
]

CHECKLIST_PATTERNS = [
    r"check\s+(list|before|after)",
    r"(installation|commissioning)\s+(guide|instruction|checklist)",
    r"safety\s+(instruction|note|warning)",
    r"(?:must|shall)\s+be\s+(checked|verified|tested)",
]

SPEC_PATTERNS = [
    r"technical\s+data",
    r"(ordering|selection)\s+(data|information|guide|table)",
    r"dimension",
    r"rated?\s+(current|voltage|power|frequency)",
    r"ambient\s+temperature",
    r"degree\s+of\s+protection\s+IP",
]

# Boilerplate to strip
BOILERPLATE_RE = re.compile(
    r"(?:Eaton\s+Wiring\s+Manual\s+\d{2}/\d{2})"
    r"|(?:PU\d+Z)"
    r"|(?:^\d{1,3}$)"  # bare page numbers
    r"|(?:www\.eaton\.com)",
    re.MULTILINE,
)


@dataclass
class KBAtom:
    """A knowledge atom destined for the rivet KB."""

    atom_type: str  # procedure, fault_code, checklist, spec, concept
    vendor: str = "Eaton"
    product: str = "Wiring Manual"
    title: str = ""
    summary: str = ""
    content: str = ""
    code: str | None = None
    symptoms: list[str] = field(default_factory=list)
    causes: list[str] = field(default_factory=list)
    fixes: list[str] = field(default_factory=list)
    pattern_type: str | None = None
    prerequisites: list[str] = field(default_factory=list)
    steps: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    difficulty: str | None = None
    source_url: str = "eaton-wiring-manual-pu08703001z"
    source_pages: str = ""


def clean_text(text: str) -> str:
    """Strip boilerplate and normalize whitespace."""
    text = BOILERPLATE_RE.sub("", text)
    # Collapse multiple blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def classify_atom_type(text: str, title: str) -> str:
    """Classify the atom type based on content patterns."""
    combined = (title + " " + text).lower()

    for pat in PROCEDURE_PATTERNS:
        if re.search(pat, combined):
            return "procedure"

    for pat in FAULT_PATTERNS:
        if re.search(pat, combined):
            return "fault_code"

    for pat in CHECKLIST_PATTERNS:
        if re.search(pat, combined):
            return "checklist"

    for pat in SPEC_PATTERNS:
        if re.search(pat, combined):
            return "spec"

    return "concept"


def extract_keywords(text: str) -> list[str]:
    """Pull out technical keywords from text."""
    # Match component designations, standards, model numbers
    patterns = [
        r"\b[A-Z]{1,4}\d{2,5}[A-Z]?\b",  # model numbers like DILM25, ZB32
        r"\bIEC\s*\d+",  # IEC standards
        r"\bEN\s*\d+",  # EN standards
        r"\bIP\s*\d{2}",  # IP ratings
        r"\b(?:NO|NC|PE|N|L[123])\b",  # terminal types
        r"\b(?:VFD|DOL|PLC|HMI)\b",  # acronyms
        r"\b\d+\s*(?:kW|HP|A|V|Hz|mm²|AWG)\b",  # rated values
    ]
    kws = set()
    for pat in patterns:
        for match in re.finditer(pat, text):
            kws.add(match.group().strip())
    return sorted(kws)[:20]


def extract_steps(text: str) -> list[str]:
    """Extract numbered steps if present."""
    steps = []
    # Pattern: lines starting with 1., 2., etc. or Step 1, Step 2
    for match in re.finditer(
        r"(?:^|\n)\s*(?:Step\s+)?(\d{1,2})[.):]\s*(.+?)(?=\n\s*(?:Step\s+)?\d{1,2}[.):]\s|\n\n|\Z)",
        text,
        re.DOTALL,
    ):
        step_text = match.group(2).strip()
        if len(step_text) > 10:  # skip trivial matches
            steps.append(step_text[:500])
    return steps[:20]


def detect_section_breaks(page_text: str) -> list[tuple[str, str]]:
    """Detect section headings and split page text into sections.

    Returns list of (heading, body) tuples.
    """
    # Heuristic: headings are typically short lines (< 80 chars) followed
    # by longer content, often in title case or ALL CAPS
    lines = page_text.split("\n")
    sections: list[tuple[str, str]] = []
    current_heading = ""
    current_body: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            current_body.append("")
            continue

        # Detect heading: short, title-case or uppercase, not a sentence
        is_heading = (
            len(stripped) < 80
            and not stripped.endswith(".")
            and not stripped.endswith(",")
            and (stripped.istitle() or stripped.isupper() or re.match(r"^\d+\.\d+", stripped))
            and len(stripped.split()) <= 12
        )

        if is_heading and current_body:
            body_text = "\n".join(current_body).strip()
            if body_text and len(body_text) > 50:
                sections.append((current_heading, body_text))
            current_heading = stripped
            current_body = []
        elif is_heading and not current_body:
            current_heading = stripped
        else:
            current_body.append(stripped)

    # Flush last section
    body_text = "\n".join(current_body).strip()
    if body_text and len(body_text) > 50:
        sections.append((current_heading, body_text))

    return sections


def extract_tables(page: fitz.Page) -> list[str]:
    """Extract tables from a page as formatted text."""
    tables = []
    try:
        found = page.find_tables()
        for table in found.tables:
            rows = table.extract()
            if rows and len(rows) > 1:
                # Format as markdown-style table
                header = rows[0]
                lines = [" | ".join(str(c or "") for c in header)]
                lines.append(" | ".join("---" for _ in header))
                for row in rows[1:]:
                    lines.append(" | ".join(str(c or "") for c in row))
                tables.append("\n".join(lines))
    except Exception:
        pass  # Not all pages have tables
    return tables


def chapter_for_page(page_num: int) -> tuple[str, str]:
    """Return (chapter_title, chapter_slug) for a 1-indexed page number."""
    for start, end, title, slug in CHAPTERS:
        if start <= page_num <= end:
            return title, slug
    return "Unknown", "unknown"


def parse_pdf(pdf_path: str) -> list[KBAtom]:
    """Parse the Eaton PDF into KB atoms."""
    doc = fitz.open(pdf_path)
    log.info("Opened %s (%d pages)", pdf_path, len(doc))

    atoms: list[KBAtom] = []
    skip_chapters = {"index", "intro"}

    for page_idx in range(len(doc)):
        page_num = page_idx + 1
        chapter_title, chapter_slug = chapter_for_page(page_num)

        if chapter_slug in skip_chapters:
            continue

        page = doc[page_idx]
        raw_text = page.get_text("text")
        if not raw_text or len(raw_text.strip()) < 100:
            continue

        text = clean_text(raw_text)
        tables = extract_tables(page)

        # Split page into sections
        sections = detect_section_breaks(text)
        if not sections:
            # Treat entire page as one section
            sections = [(chapter_title, text)]

        for heading, body in sections:
            if len(body) < 80:
                continue

            title = heading if heading else f"{chapter_title} (p.{page_num})"

            # Include table data in content
            content = body
            if tables:
                content += "\n\n" + "\n\n".join(tables)

            atom_type = classify_atom_type(content, title)
            keywords = extract_keywords(content)
            steps = extract_steps(content) if atom_type == "procedure" else []

            # Build summary (first 300 chars of body, cleaned)
            summary_text = body[:300].replace("\n", " ").strip()
            if len(body) > 300:
                summary_text += "..."

            atom = KBAtom(
                atom_type=atom_type,
                title=title[:200],
                summary=summary_text,
                content=content[:5000],
                keywords=keywords,
                steps=steps,
                source_pages=str(page_num),
                pattern_type=chapter_slug,
            )

            # Add chapter as keyword
            if chapter_slug not in atom.keywords:
                atom.keywords.append(chapter_slug)

            atoms.append(atom)

        if page_num % 50 == 0:
            log.info("Processed %d/%d pages (%d atoms so far)", page_num, len(doc), len(atoms))

    num_pages = len(doc)
    doc.close()
    log.info("Extracted %d atoms from %d pages", len(atoms), num_pages)
    return atoms


def merge_small_atoms(atoms: list[KBAtom], min_content_length: int = 200) -> list[KBAtom]:
    """Merge atoms with very small content into their neighbors."""
    if not atoms:
        return atoms

    merged: list[KBAtom] = []
    buffer: KBAtom | None = None

    for atom in atoms:
        if len(atom.content) < min_content_length and buffer:
            # Merge into buffer
            buffer.content += "\n\n" + atom.content
            buffer.summary += " " + atom.summary
            buffer.keywords = list(set(buffer.keywords + atom.keywords))[:20]
            if atom.steps:
                buffer.steps.extend(atom.steps)
            # Update source_pages range
            buffer.source_pages = f"{buffer.source_pages}-{atom.source_pages}"
        elif len(atom.content) < min_content_length and not buffer:
            buffer = atom
        else:
            if buffer:
                merged.append(buffer)
                buffer = None
            merged.append(atom)

    if buffer:
        merged.append(buffer)

    return merged


def deduplicate_atoms(atoms: list[KBAtom]) -> list[KBAtom]:
    """Remove atoms with near-identical titles and content."""
    seen_titles: set[str] = set()
    deduped: list[KBAtom] = []

    for atom in atoms:
        # Normalize title for comparison
        norm_title = re.sub(r"\s+", " ", atom.title.lower().strip())
        if norm_title in seen_titles:
            continue
        seen_titles.add(norm_title)
        deduped.append(atom)

    return deduped


def main():
    parser = argparse.ArgumentParser(description="Parse Eaton Wiring Manual into KB atoms")
    default_pdf = os.path.expanduser(
        "~/Downloads/eaton-wiring-manual-pu08703001z-en-en-us.pdf"
    )
    # Also check Windows-style path
    if not os.path.exists(default_pdf):
        win_pdf = "/mnt/c/Users/hharp/Downloads/eaton-wiring-manual-pu08703001z-en-en-us.pdf"
        if os.path.exists(win_pdf):
            default_pdf = win_pdf

    parser.add_argument("--pdf", default=default_pdf, help="Path to Eaton PDF")
    parser.add_argument("--output", default="eaton_atoms.json", help="Output JSON path")
    parser.add_argument("--min-content", type=int, default=200, help="Min content length per atom")
    args = parser.parse_args()

    if not os.path.exists(args.pdf):
        log.error("PDF not found: %s", args.pdf)
        sys.exit(1)

    # Parse
    atoms = parse_pdf(args.pdf)

    # Post-process
    log.info("Merging small atoms (min %d chars)...", args.min_content)
    atoms = merge_small_atoms(atoms, args.min_content)

    log.info("Deduplicating...")
    atoms = deduplicate_atoms(atoms)

    # Stats
    type_counts: dict[str, int] = {}
    for a in atoms:
        type_counts[a.atom_type] = type_counts.get(a.atom_type, 0) + 1

    log.info("Final: %d atoms", len(atoms))
    for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
        log.info("  %s: %d", t, c)

    # Write JSON
    output = [asdict(a) for a in atoms]
    with open(args.output, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    log.info("Written to %s", args.output)


if __name__ == "__main__":
    main()
