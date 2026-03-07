#!/usr/bin/env python3
"""Batch ingestion pipeline for FactoryLM knowledge base.

Scans kb/sources/ for documents, chunks them semantically, and feeds
each chunk into the Mem0 brain (Neon pgvector + Gemini embeddings).

Usage:
    python kb/ingest.py                    # ingest all new/changed files
    python kb/ingest.py --force            # re-ingest everything
    python kb/ingest.py --dry-run          # show what would be ingested
    python kb/ingest.py path/to/file.md    # ingest a single file

Requires: NEON_DATABASE_URL, GEMINI_API_KEY, GROQ_API_KEY (via Doppler or env)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
from pathlib import Path
from typing import Any

# Ensure monorepo root is importable
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from kb.chunker import chunk_file  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("kb.ingest")

SOURCES_DIR = Path(__file__).parent / "sources"
STATE_FILE = Path(__file__).parent / ".ingest_state.json"
SUPPORTED_EXTENSIONS = {".md", ".txt", ".rst"}


def _file_hash(path: Path) -> str:
    """SHA-256 of file contents."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_state() -> dict[str, Any]:
    """Load ingestion state (which files have been processed)."""
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {}


def _save_state(state: dict[str, Any]) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _get_mem0():
    """Get the Mem0 Memory client using existing brain config."""
    from services.brain.config import get_memory
    return get_memory()


def _collect_files(target: str | None = None) -> list[Path]:
    """Collect files to ingest."""
    if target:
        p = Path(target)
        if not p.exists():
            log.error("File not found: %s", target)
            return []
        return [p]

    if not SOURCES_DIR.exists():
        log.warning("Sources directory not found: %s", SOURCES_DIR)
        return []

    files = []
    for ext in SUPPORTED_EXTENSIONS:
        files.extend(SOURCES_DIR.rglob(f"*{ext}"))
    return sorted(files)


def ingest(
    target: str | None = None,
    force: bool = False,
    dry_run: bool = False,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
) -> dict[str, Any]:
    """Run the ingestion pipeline.

    Returns summary dict with counts.
    """
    files = _collect_files(target)
    if not files:
        log.info("No files to ingest.")
        return {"files": 0, "chunks": 0, "skipped": 0}

    state = _load_state()
    mem = None if dry_run else _get_mem0()

    total_chunks = 0
    skipped = 0
    ingested_files = 0

    for path in files:
        file_hash = _file_hash(path)
        file_key = str(path.resolve())

        # Skip unchanged files unless forced
        if not force and state.get(file_key, {}).get("hash") == file_hash:
            log.info("SKIP (unchanged): %s", path.name)
            skipped += 1
            continue

        log.info("INGEST: %s", path.name)
        chunks = chunk_file(path, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        log.info("  → %d chunks", len(chunks))

        if dry_run:
            for i, chunk in enumerate(chunks):
                log.info("  [%d] %d chars | section=%s | equipment=%s",
                         i, len(chunk.text),
                         chunk.metadata.get("section", "-"),
                         chunk.metadata.get("equipment", []))
        else:
            for chunk in chunks:
                tags = chunk.metadata.get("equipment", [])
                mem.add(
                    chunk.text,
                    user_id="mike",
                    metadata={
                        "source": "kb_ingest",
                        "file": str(path),
                        "section": chunk.metadata.get("section", ""),
                        "equipment": tags,
                        "chunk_index": chunk.metadata.get("chunk_index", 0),
                        "tags": ["kb", "document"] + tags,
                    },
                )

            state[file_key] = {
                "hash": file_hash,
                "chunks": len(chunks),
                "file": path.name,
            }

        total_chunks += len(chunks)
        ingested_files += 1

    if not dry_run:
        _save_state(state)

    summary = {
        "files": ingested_files,
        "chunks": total_chunks,
        "skipped": skipped,
    }
    log.info("Done: %d files, %d chunks ingested, %d skipped", **summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description="FactoryLM KB ingestion pipeline")
    parser.add_argument("file", nargs="?", help="Single file to ingest (default: scan kb/sources/)")
    parser.add_argument("--force", action="store_true", help="Re-ingest all files regardless of hash")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be ingested without writing")
    parser.add_argument("--chunk-size", type=int, default=1000, help="Chunk size in chars (default: 1000)")
    parser.add_argument("--chunk-overlap", type=int, default=200, help="Overlap between chunks (default: 200)")
    args = parser.parse_args()

    result = ingest(
        target=args.file,
        force=args.force,
        dry_run=args.dry_run,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
