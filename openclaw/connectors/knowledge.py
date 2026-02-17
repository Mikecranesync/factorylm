"""Knowledge Base connector with dual-write to rivet + neon.

Wraps access to:
- knowledge_atoms table (rivet PostgreSQL) — structured search, specs
- entities table (neon PostgreSQL) — semantic/embedding search

Reuses query patterns from workers/manual_hunter_tasks.py.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Any, Optional

log = logging.getLogger(__name__)

# Database configuration (from workers/manual_hunter_tasks.py pattern)
RIVET_DB_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": int(os.getenv("POSTGRES_PORT", "5432")),
    "database": os.getenv("POSTGRES_DB", "rivet"),
    "user": os.getenv("POSTGRES_USER", "rivet"),
    "password": os.getenv("POSTGRES_PASSWORD", "rivet_factory_2025!"),
}

NEON_DB_URL = os.getenv(
    "NEON_DATABASE_URL",
    "",  # Must be set for semantic search
)

# SQL for knowledge_atoms operations
SEARCH_SQL = """
    SELECT atom_id, atom_type, vendor, product, title,
           LEFT(summary, 500) as summary, content,
           keywords, part_number, wiring_model, needs_review,
           ts_rank(to_tsvector('english', title || ' ' || summary || ' ' || content),
                   plainto_tsquery('english', %s)) as rank
    FROM knowledge_atoms
    WHERE to_tsvector('english', title || ' ' || summary || ' ' || content)
          @@ plainto_tsquery('english', %s)
"""

FIND_BY_PART_SQL = """
    SELECT atom_id, atom_type, vendor, product, title, summary, content,
           keywords, part_number, wiring_model, manual_refs, provenance,
           needs_review
    FROM knowledge_atoms
    WHERE vendor ILIKE %s AND (product ILIKE %s OR part_number ILIKE %s)
    LIMIT 1
"""

INSERT_ATOM_SQL = """
    INSERT INTO knowledge_atoms (
        atom_type, vendor, product, part_number, title, summary, content,
        keywords, wiring_model, manual_refs, provenance, needs_review
    ) VALUES (
        %s, %s, %s, %s, %s, %s, %s,
        %s, %s, %s, %s, %s
    ) RETURNING atom_id
"""

UPDATE_ATOM_SQL = """
    UPDATE knowledge_atoms SET
        summary = COALESCE(%s, summary),
        content = COALESCE(%s, content),
        keywords = COALESCE(%s, keywords),
        wiring_model = COALESCE(%s, wiring_model),
        manual_refs = COALESCE(%s, manual_refs),
        provenance = COALESCE(%s, provenance),
        needs_review = %s
    WHERE atom_id = %s
"""

# SQL for schema migration (run once)
SCHEMA_MIGRATION_SQL = """
    ALTER TABLE knowledge_atoms ADD COLUMN IF NOT EXISTS part_number VARCHAR(100);
    ALTER TABLE knowledge_atoms ADD COLUMN IF NOT EXISTS wiring_model JSONB DEFAULT '{}';
    ALTER TABLE knowledge_atoms ADD COLUMN IF NOT EXISTS manual_refs TEXT[] DEFAULT '{}';
    ALTER TABLE knowledge_atoms ADD COLUMN IF NOT EXISTS provenance JSONB DEFAULT '[]';
    ALTER TABLE knowledge_atoms ADD COLUMN IF NOT EXISTS needs_review BOOLEAN DEFAULT FALSE;
"""


class KnowledgeConnector:
    """Dual-write connector for knowledge_atoms (rivet) + entities (neon)."""

    def __init__(
        self,
        db_config: Optional[dict] = None,
        neon_url: Optional[str] = None,
    ):
        self._rivet_config = db_config or RIVET_DB_CONFIG
        self._neon_url = neon_url or NEON_DB_URL
        self._rivet_conn = None
        self._neon_conn = None
        self._migrated = False

    def _get_rivet(self):
        """Get or create rivet DB connection."""
        if self._rivet_conn is None or self._rivet_conn.closed:
            try:
                import psycopg2
                self._rivet_conn = psycopg2.connect(**self._rivet_config)
                if not self._migrated:
                    self._run_migration()
            except ImportError:
                log.error("psycopg2 not installed: pip install psycopg2-binary")
                return None
            except Exception as e:
                log.error("Rivet DB connection failed: %s", e)
                return None
        return self._rivet_conn

    def _get_neon(self):
        """Get or create neon DB connection (for entities table)."""
        if not self._neon_url:
            return None
        if self._neon_conn is None or self._neon_conn.closed:
            try:
                import psycopg2
                self._neon_conn = psycopg2.connect(self._neon_url)
            except Exception as e:
                log.warning("Neon DB connection failed: %s", e)
                return None
        return self._neon_conn

    def _run_migration(self) -> None:
        """Add new columns to knowledge_atoms if they don't exist."""
        conn = self._rivet_conn
        if not conn:
            return
        try:
            cur = conn.cursor()
            for stmt in SCHEMA_MIGRATION_SQL.strip().split(";"):
                stmt = stmt.strip()
                if stmt:
                    cur.execute(stmt)
            conn.commit()
            cur.close()
            self._migrated = True
            log.info("KB schema migration complete")
        except Exception as e:
            log.warning("Schema migration skipped: %s", e)
            conn.rollback()

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        vendor: Optional[str] = None,
        limit: int = 5,
    ) -> list[dict]:
        """Full-text search on knowledge_atoms table.

        Reuses the ManualHunter.search_fulltext pattern.
        """
        conn = self._get_rivet()
        if not conn:
            return []

        try:
            cur = conn.cursor()
            sql = SEARCH_SQL
            params: list = [query, query]

            if vendor:
                sql += " AND (vendor ILIKE %s OR product ILIKE %s)"
                params.extend([f"%{vendor}%", f"%{vendor}%"])

            sql += " ORDER BY rank DESC LIMIT %s"
            params.append(limit)

            cur.execute(sql, params)
            columns = [desc[0] for desc in cur.description]
            results = [dict(zip(columns, row)) for row in cur.fetchall()]
            cur.close()

            # Parse JSONB fields
            for r in results:
                if isinstance(r.get("wiring_model"), str):
                    try:
                        r["wiring_model"] = json.loads(r["wiring_model"])
                    except (json.JSONDecodeError, TypeError):
                        pass

            return results
        except Exception as e:
            log.error("KB search failed: %s", e)
            conn.rollback()
            return []

    def find_by_part(
        self,
        vendor: str,
        part_number: str,
    ) -> Optional[dict]:
        """Look up a component by vendor + part number."""
        conn = self._get_rivet()
        if not conn:
            return None

        try:
            cur = conn.cursor()
            cur.execute(FIND_BY_PART_SQL, [
                f"%{vendor}%",
                f"%{part_number}%",
                f"%{part_number}%",
            ])
            row = cur.fetchone()
            cur.close()

            if not row:
                return None

            columns = [desc[0] for desc in cur.description]
            result = dict(zip(columns, row))

            # Parse JSONB fields
            for field in ("wiring_model", "provenance"):
                if isinstance(result.get(field), str):
                    try:
                        result[field] = json.loads(result[field])
                    except (json.JSONDecodeError, TypeError):
                        pass

            return result
        except Exception as e:
            log.error("KB find_by_part failed: %s", e)
            conn.rollback()
            return None

    # ------------------------------------------------------------------
    # Insert
    # ------------------------------------------------------------------

    def insert_atom(self, atom_data: dict) -> Optional[int]:
        """Insert a new atom into knowledge_atoms + entities.

        Returns the new atom_id from knowledge_atoms.
        """
        conn = self._get_rivet()
        if not conn:
            return None

        try:
            cur = conn.cursor()

            # Build content string from structured data
            content = atom_data.get("content", "")
            if not content and atom_data.get("terminals"):
                content = _build_content_string(atom_data)

            cur.execute(INSERT_ATOM_SQL, [
                atom_data.get("atom_type", "spec"),
                atom_data.get("vendor", ""),
                atom_data.get("product", ""),
                atom_data.get("part_number", ""),
                atom_data.get("title", f"{atom_data.get('vendor', '')} {atom_data.get('product', '')}"),
                atom_data.get("summary", ""),
                content[:5000],
                atom_data.get("keywords", []),
                json.dumps(atom_data.get("wiring_model", {})),
                atom_data.get("manual_refs", []),
                json.dumps(atom_data.get("provenance", [])),
                atom_data.get("needs_review", False),
            ])

            atom_id = cur.fetchone()[0]
            conn.commit()
            cur.close()

            log.info("Inserted KB atom %d: %s %s",
                     atom_id, atom_data.get("vendor"), atom_data.get("product"))

            # Also insert into entities (neon) if available
            self._insert_entity(atom_data, atom_id)

            return atom_id

        except Exception as e:
            log.error("KB insert failed: %s", e)
            conn.rollback()
            return None

    def _insert_entity(self, atom_data: dict, atom_id: int) -> None:
        """Insert into the entities table (neon) for semantic search."""
        conn = self._get_neon()
        if not conn:
            return

        try:
            cur = conn.cursor()
            content = atom_data.get("content", "")
            if not content:
                content = _build_content_string(atom_data)

            cur.execute("""
                INSERT INTO entities (type, content, summary, source, source_id, metadata)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, [
                "component_spec",
                content[:5000],
                f"{atom_data.get('vendor', '')} {atom_data.get('product', '')}",
                "kb_enrichment",
                str(atom_id),
                json.dumps({
                    "vendor": atom_data.get("vendor"),
                    "part_number": atom_data.get("part_number"),
                    "atom_id": atom_id,
                    "wiring_model": atom_data.get("wiring_model", {}),
                }),
            ])
            conn.commit()
            cur.close()
            log.info("Inserted entity for atom %d", atom_id)
        except Exception as e:
            log.warning("Entity insert failed (neon): %s", e)
            conn.rollback()

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def update_atom(
        self,
        atom_id: int,
        updates: dict,
        provenance: Optional[dict] = None,
        conflict: bool = False,
    ) -> bool:
        """Update an existing KB atom.

        If conflict=True, sets needs_review=True instead of overwriting.
        """
        conn = self._get_rivet()
        if not conn:
            return False

        try:
            # First, read existing provenance to append
            cur = conn.cursor()
            cur.execute("SELECT provenance FROM knowledge_atoms WHERE atom_id = %s", [atom_id])
            row = cur.fetchone()
            existing_provenance = []
            if row and row[0]:
                existing_provenance = row[0] if isinstance(row[0], list) else json.loads(row[0])

            if provenance:
                existing_provenance.append(provenance)

            cur.execute(UPDATE_ATOM_SQL, [
                updates.get("summary"),
                updates.get("content"),
                updates.get("keywords"),
                json.dumps(updates["wiring_model"]) if "wiring_model" in updates else None,
                updates.get("manual_refs"),
                json.dumps(existing_provenance),
                conflict,  # needs_review
                atom_id,
            ])
            conn.commit()
            cur.close()

            log.info("Updated KB atom %d (conflict=%s)", atom_id, conflict)

            # Also update entities table
            self._update_entity(atom_id, updates)

            return True
        except Exception as e:
            log.error("KB update failed: %s", e)
            conn.rollback()
            return False

    def _update_entity(self, atom_id: int, updates: dict) -> None:
        """Update the corresponding entity in neon."""
        conn = self._get_neon()
        if not conn:
            return

        try:
            cur = conn.cursor()
            metadata_updates = {}
            if "wiring_model" in updates:
                metadata_updates["wiring_model"] = updates["wiring_model"]

            if metadata_updates:
                cur.execute("""
                    UPDATE entities
                    SET metadata = metadata || %s::jsonb,
                        updated_at = NOW()
                    WHERE source = 'kb_enrichment' AND source_id = %s
                """, [json.dumps(metadata_updates), str(atom_id)])

            if updates.get("content"):
                cur.execute("""
                    UPDATE entities SET content = %s, updated_at = NOW()
                    WHERE source = 'kb_enrichment' AND source_id = %s
                """, [updates["content"][:5000], str(atom_id)])

            conn.commit()
            cur.close()
        except Exception as e:
            log.warning("Entity update failed (neon): %s", e)
            conn.rollback()

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Get KB statistics."""
        conn = self._get_rivet()
        if not conn:
            return {"error": "No database connection"}

        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT
                    COUNT(*) as total_atoms,
                    COUNT(DISTINCT vendor) as vendors,
                    COUNT(DISTINCT product) as products,
                    COUNT(CASE WHEN needs_review THEN 1 END) as needs_review
                FROM knowledge_atoms
            """)
            row = cur.fetchone()
            cur.close()

            return {
                "total_atoms": row[0],
                "vendors": row[1],
                "products": row[2],
                "needs_review": row[3],
            }
        except Exception as e:
            log.error("KB stats failed: %s", e)
            return {"error": str(e)}

    def close(self) -> None:
        """Close all database connections."""
        if self._rivet_conn and not self._rivet_conn.closed:
            self._rivet_conn.close()
        if self._neon_conn and not self._neon_conn.closed:
            self._neon_conn.close()


def _build_content_string(atom_data: dict) -> str:
    """Build a human-readable content string from structured atom data."""
    parts = [
        f"Component: {atom_data.get('product', '')}",
        f"Vendor: {atom_data.get('vendor', '')}",
    ]

    if atom_data.get("part_number"):
        parts.append(f"Part Number: {atom_data['part_number']}")

    ratings = atom_data.get("ratings", {})
    if ratings:
        for k, v in ratings.items():
            if v:
                parts.append(f"{k.replace('_', ' ').title()}: {v}")

    terminals = atom_data.get("terminals", {})
    if terminals:
        parts.append("")
        parts.append("Terminal Layout:")
        for tid, info in sorted(terminals.items()):
            label = info.get("label", "") if isinstance(info, dict) else str(info)
            parts.append(f"  Terminal {tid}: {label}")

    wiring_model = atom_data.get("wiring_model", {})
    if wiring_model:
        parts.append("")
        parts.append("Wiring Model:")
        parts.append(json.dumps(wiring_model, indent=2))

    return "\n".join(parts)
