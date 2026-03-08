#!/usr/bin/env python3
"""Load Eaton KB atoms into the rivet PostgreSQL knowledge_atoms table.

Reads the JSON output from parse_eaton_manual.py and inserts into the
knowledge_atoms table in the rivet database.

Usage:
    python scripts/load_kb_atoms.py [--input PATH] [--db-url URL] [--dry-run]

Defaults:
    --input   eaton_atoms.json
    --db-url  postgresql://rivet:rivet_factory_2025!@localhost:5432/rivet
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys

try:
    import asyncpg
except ImportError:
    print("asyncpg required: pip install asyncpg", file=sys.stderr)
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

DEFAULT_DB_URL = "postgresql://rivet:rivet_factory_2025!@localhost:5432/rivet"

INSERT_SQL = """
INSERT INTO knowledge_atoms (
    atom_type, vendor, product, title, summary, content,
    code, symptoms, causes, fixes,
    pattern_type, prerequisites, steps, keywords,
    difficulty, source_url, source_pages
) VALUES (
    $1, $2, $3, $4, $5, $6,
    $7, $8, $9, $10,
    $11, $12, $13, $14,
    $15, $16, $17
)
"""


async def load_atoms(input_path: str, db_url: str, dry_run: bool = False):
    """Load atoms from JSON into PostgreSQL."""
    with open(input_path) as f:
        atoms = json.load(f)

    log.info("Loaded %d atoms from %s", len(atoms), input_path)

    if dry_run:
        # Just show stats
        type_counts: dict[str, int] = {}
        for a in atoms:
            t = a.get("atom_type", "unknown")
            type_counts[t] = type_counts.get(t, 0) + 1
        for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
            log.info("  %s: %d", t, c)
        log.info("Dry run — no database changes.")
        return

    conn = await asyncpg.connect(db_url)

    # Check existing Eaton atoms
    existing = await conn.fetchval(
        "SELECT count(*) FROM knowledge_atoms WHERE vendor = 'Eaton'"
    )
    if existing > 0:
        log.warning("Found %d existing Eaton atoms. Deleting before reload...", existing)
        await conn.execute("DELETE FROM knowledge_atoms WHERE vendor = 'Eaton'")
        log.info("Deleted %d existing Eaton atoms.", existing)

    # Insert in batches
    batch_size = 100
    inserted = 0

    for i in range(0, len(atoms), batch_size):
        batch = atoms[i : i + batch_size]
        records = []
        for a in batch:
            records.append((
                a.get("atom_type", "concept"),
                a.get("vendor", "Eaton"),
                a.get("product", "Wiring Manual"),
                a.get("title", "")[:200],
                a.get("summary", "")[:2000],
                a.get("content", "")[:5000],
                a.get("code"),
                a.get("symptoms") or [],
                a.get("causes") or [],
                a.get("fixes") or [],
                a.get("pattern_type"),
                a.get("prerequisites") or [],
                a.get("steps") or [],
                a.get("keywords") or [],
                a.get("difficulty"),
                a.get("source_url", ""),
                a.get("source_pages", ""),
            ))

        await conn.executemany(INSERT_SQL, records)
        inserted += len(records)
        if inserted % 500 == 0:
            log.info("Inserted %d/%d atoms...", inserted, len(atoms))

    log.info("Inserted %d atoms total.", inserted)

    # Verify
    total = await conn.fetchval("SELECT count(*) FROM knowledge_atoms")
    eaton_count = await conn.fetchval(
        "SELECT count(*) FROM knowledge_atoms WHERE vendor = 'Eaton'"
    )
    log.info("DB totals: %d total atoms, %d Eaton atoms", total, eaton_count)

    # Show type breakdown
    types = await conn.fetch(
        "SELECT atom_type, count(*) as cnt FROM knowledge_atoms "
        "WHERE vendor = 'Eaton' GROUP BY atom_type ORDER BY cnt DESC"
    )
    for t in types:
        log.info("  %s: %d", t["atom_type"], t["cnt"])

    await conn.close()


def main():
    parser = argparse.ArgumentParser(description="Load Eaton KB atoms into PostgreSQL")
    parser.add_argument("--input", default="eaton_atoms.json", help="Input JSON path")
    parser.add_argument("--db-url", default=DEFAULT_DB_URL, help="PostgreSQL URL")
    parser.add_argument("--dry-run", action="store_true", help="Just show stats, don't insert")
    args = parser.parse_args()

    asyncio.run(load_atoms(args.input, args.db_url, args.dry_run))


if __name__ == "__main__":
    main()
