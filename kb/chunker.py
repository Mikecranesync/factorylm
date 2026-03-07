"""Semantic document chunker for FactoryLM knowledge base.

Splits documents into overlapping chunks that preserve structure
(headings, sections) and extract equipment metadata.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Chunk:
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


# Separators tried in order — most structural first
_SEPARATORS = ["\n\n", "\n", ". ", " "]

# Equipment vendor patterns for metadata enrichment
_VENDOR_PATTERNS = re.compile(
    r"\b(Allen-Bradley|Rockwell|Siemens|ABB|Yaskawa|Danfoss|WEG|Baldor|"
    r"Grundfos|Flowserve|Omron|Mitsubishi|Micro\s?820|CompactLogix|"
    r"S7-\d{3,4}|MicroLogix|PowerFlex|VFD|PLC)\b",
    re.IGNORECASE,
)

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)


def _extract_equipment(text: str) -> list[str]:
    """Extract equipment/vendor mentions from text."""
    return list({m.group(0) for m in _VENDOR_PATTERNS.finditer(text)})


def _current_heading(text: str, pos: int) -> str | None:
    """Find the most recent markdown heading before pos."""
    best = None
    for m in _HEADING_RE.finditer(text):
        if m.start() <= pos:
            best = m.group(2).strip()
        else:
            break
    return best


def _split_text(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    """Recursively split text using hierarchical separators."""
    if len(text) <= chunk_size:
        return [text]

    for sep in _SEPARATORS:
        parts = text.split(sep)
        if len(parts) == 1:
            continue

        chunks: list[str] = []
        current = ""

        for part in parts:
            candidate = current + sep + part if current else part
            if len(candidate) <= chunk_size:
                current = candidate
            else:
                if current:
                    chunks.append(current)
                if len(part) > chunk_size:
                    chunks.extend(_split_text(part, chunk_size, chunk_overlap))
                    current = ""
                else:
                    current = part

        if current:
            chunks.append(current)

        if len(chunks) > 1:
            # Add overlap between consecutive chunks
            if chunk_overlap > 0:
                overlapped: list[str] = []
                for i, chunk in enumerate(chunks):
                    if i > 0:
                        prev = chunks[i - 1]
                        overlap_text = prev[-chunk_overlap:]
                        # Find a clean break point in the overlap
                        break_point = overlap_text.find(" ")
                        if break_point > 0:
                            overlap_text = overlap_text[break_point + 1:]
                        chunk = overlap_text + " " + chunk
                    overlapped.append(chunk.strip())
                return overlapped
            return chunks

    # Last resort: hard split
    return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size - chunk_overlap)]


def chunk_document(
    text: str,
    *,
    source: str = "",
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
    extra_metadata: dict[str, Any] | None = None,
) -> list[Chunk]:
    """Chunk a document into overlapping pieces with metadata.

    Args:
        text: Document content.
        source: Source file path or identifier.
        chunk_size: Target chunk size in characters.
        chunk_overlap: Overlap between consecutive chunks.
        extra_metadata: Additional metadata to attach to every chunk.

    Returns:
        List of Chunk objects with text and metadata.
    """
    raw_chunks = _split_text(text, chunk_size, chunk_overlap)

    results: list[Chunk] = []
    for i, raw in enumerate(raw_chunks):
        stripped = raw.strip()
        if not stripped or len(stripped) < 30:
            continue

        # Find position in original text for heading context
        pos = text.find(stripped[:50])
        heading = _current_heading(text, pos) if pos >= 0 else None

        equipment = _extract_equipment(stripped)

        meta: dict[str, Any] = {
            "source": source,
            "chunk_index": i,
            "total_chunks": len(raw_chunks),
        }
        if heading:
            meta["section"] = heading
        if equipment:
            meta["equipment"] = equipment
        if extra_metadata:
            meta.update(extra_metadata)

        results.append(Chunk(text=stripped, metadata=meta))

    return results


def chunk_file(
    path: str | Path,
    *,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
    extra_metadata: dict[str, Any] | None = None,
) -> list[Chunk]:
    """Read a file and chunk it."""
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    return chunk_document(
        text,
        source=str(path),
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        extra_metadata=extra_metadata,
    )
