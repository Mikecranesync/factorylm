"""Database operations for troubleshoot trees (rivet PostgreSQL)."""

from __future__ import annotations

import json
import logging
import os

from openclaw.troubleshoot.models import TroubleshootTree

logger = logging.getLogger(__name__)

RIVET_DB_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": int(os.getenv("POSTGRES_PORT", "5432")),
    "database": os.getenv("POSTGRES_DB", "rivet"),
    "user": os.getenv("POSTGRES_USER", "rivet"),
    "password": os.getenv("POSTGRES_PASSWORD", "rivet_factory_2025!"),
}

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS troubleshoot_trees (
    tree_id       SERIAL PRIMARY KEY,
    slug          VARCHAR(100) UNIQUE NOT NULL,
    title         VARCHAR(255) NOT NULL,
    description   TEXT DEFAULT '',
    fault_codes   TEXT[] DEFAULT '{}',
    trigger_words TEXT[] DEFAULT '{}',
    equipment     VARCHAR(100) DEFAULT '',
    tree          JSONB NOT NULL,
    version       INTEGER DEFAULT 1,
    is_active     BOOLEAN DEFAULT TRUE,
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    updated_at    TIMESTAMPTZ DEFAULT NOW()
);
"""

CREATE_INDEXES_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_tt_fault_codes ON troubleshoot_trees USING GIN (fault_codes);",
    "CREATE INDEX IF NOT EXISTS idx_tt_trigger_words ON troubleshoot_trees USING GIN (trigger_words);",
]

UPSERT_SQL = """
INSERT INTO troubleshoot_trees (slug, title, description, fault_codes, trigger_words, equipment, tree, version, is_active, updated_at)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
ON CONFLICT (slug) DO UPDATE SET
    title = EXCLUDED.title,
    description = EXCLUDED.description,
    fault_codes = EXCLUDED.fault_codes,
    trigger_words = EXCLUDED.trigger_words,
    equipment = EXCLUDED.equipment,
    tree = EXCLUDED.tree,
    version = EXCLUDED.version,
    is_active = EXCLUDED.is_active,
    updated_at = NOW()
RETURNING tree_id;
"""

LOAD_ALL_SQL = """
SELECT tree_id, slug, title, description, fault_codes, trigger_words,
       equipment, tree, version, is_active
FROM troubleshoot_trees
WHERE is_active = TRUE
ORDER BY slug;
"""


def _get_conn():
    """Get a psycopg2 connection to rivet DB."""
    import psycopg2
    return psycopg2.connect(**RIVET_DB_CONFIG)


def create_schema() -> None:
    """Create the troubleshoot_trees table and indexes if they don't exist."""
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute(CREATE_TABLE_SQL)
        for idx_sql in CREATE_INDEXES_SQL:
            cur.execute(idx_sql)
        conn.commit()
        cur.close()
        logger.info("troubleshoot_trees schema ready")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def load_all_trees() -> list[TroubleshootTree]:
    """Load all active trees from the database."""
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute(LOAD_ALL_SQL)
        columns = [desc[0] for desc in cur.description]
        rows = [dict(zip(columns, row)) for row in cur.fetchall()]
        cur.close()
        trees = [TroubleshootTree.from_db_row(row) for row in rows]
        logger.info("Loaded %d troubleshoot trees from DB", len(trees))
        return trees
    except Exception:
        logger.exception("Failed to load troubleshoot trees")
        return []
    finally:
        conn.close()


def upsert_tree(tree_data: dict) -> int | None:
    """Insert or update a troubleshoot tree. Returns tree_id."""
    conn = _get_conn()
    try:
        cur = conn.cursor()
        tree_json = json.dumps({
            "root": tree_data["tree"]["root"],
            "nodes": tree_data["tree"]["nodes"],
        })
        cur.execute(UPSERT_SQL, [
            tree_data["slug"],
            tree_data["title"],
            tree_data.get("description", ""),
            tree_data.get("fault_codes", []),
            tree_data.get("trigger_words", []),
            tree_data.get("equipment", ""),
            tree_json,
            tree_data.get("version", 1),
            tree_data.get("is_active", True),
        ])
        tree_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        logger.info("Upserted tree '%s' (id=%d)", tree_data["slug"], tree_id)
        return tree_id
    except Exception:
        conn.rollback()
        logger.exception("Failed to upsert tree '%s'", tree_data.get("slug", "?"))
        return None
    finally:
        conn.close()
