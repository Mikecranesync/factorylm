"""
SQLite storage for opportunities.
"""

import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from .models import Opportunity, OpportunityStatus, RAGStatus


class OpportunitiesStorage:
    """SQLite CRUD operations for opportunities."""

    def __init__(self, db_path: Optional[str] = None):
        """Initialize storage with database path."""
        if db_path is None:
            db_path = os.environ.get(
                "OPPORTUNITIES_DB_PATH",
                os.path.expanduser("~/.factorylm/opportunities.db")
            )
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        """Get database connection with row factory."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Initialize database schema."""
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS opportunities (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    organizer TEXT,
                    type TEXT NOT NULL,
                    url TEXT,
                    cfp_deadline TEXT,
                    application_deadline TEXT,
                    registration_deadline TEXT,
                    event_start TEXT,
                    event_end TEXT,
                    timezone TEXT DEFAULT 'America/New_York',
                    location TEXT,
                    is_virtual INTEGER DEFAULT 0,
                    source TEXT,
                    source_url TEXT,
                    status TEXT DEFAULT 'discovered',
                    google_event_ids TEXT,
                    progress_percent INTEGER DEFAULT 0,
                    rag_status TEXT DEFAULT 'grey',
                    materials_checklist TEXT,
                    notes TEXT,
                    tags TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_opportunities_status
                ON opportunities(status)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_opportunities_source
                ON opportunities(source)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_opportunities_cfp_deadline
                ON opportunities(cfp_deadline)
            """)
            conn.commit()

    def create(self, opp: Opportunity) -> Opportunity:
        """Create a new opportunity."""
        opp.updated_at = datetime.utcnow()
        data = opp.to_dict()

        columns = ", ".join(data.keys())
        placeholders = ", ".join(["?" for _ in data])

        with self._get_conn() as conn:
            conn.execute(
                f"INSERT INTO opportunities ({columns}) VALUES ({placeholders})",
                list(data.values())
            )
            conn.commit()
        return opp

    def get(self, opp_id: str) -> Optional[Opportunity]:
        """Get opportunity by ID."""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM opportunities WHERE id = ?",
                (opp_id,)
            ).fetchone()
            if row:
                return Opportunity.from_dict(dict(row))
        return None

    def get_by_name(self, name: str) -> Optional[Opportunity]:
        """Get opportunity by name (exact match)."""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM opportunities WHERE name = ?",
                (name,)
            ).fetchone()
            if row:
                return Opportunity.from_dict(dict(row))
        return None

    def update(self, opp: Opportunity) -> Opportunity:
        """Update an existing opportunity."""
        opp.updated_at = datetime.utcnow()
        data = opp.to_dict()
        opp_id = data.pop("id")

        set_clause = ", ".join([f"{k} = ?" for k in data.keys()])

        with self._get_conn() as conn:
            conn.execute(
                f"UPDATE opportunities SET {set_clause} WHERE id = ?",
                list(data.values()) + [opp_id]
            )
            conn.commit()
        return opp

    def upsert(self, opp: Opportunity) -> Opportunity:
        """Insert or update opportunity (match by name + source)."""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT id FROM opportunities WHERE name = ? AND source = ?",
                (opp.name, opp.source)
            ).fetchone()
            if row:
                opp.id = row["id"]
                return self.update(opp)
            return self.create(opp)

    def delete(self, opp_id: str) -> bool:
        """Delete an opportunity."""
        with self._get_conn() as conn:
            cursor = conn.execute(
                "DELETE FROM opportunities WHERE id = ?",
                (opp_id,)
            )
            conn.commit()
            return cursor.rowcount > 0

    def list_all(self) -> List[Opportunity]:
        """List all opportunities."""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM opportunities ORDER BY cfp_deadline ASC"
            ).fetchall()
            return [Opportunity.from_dict(dict(row)) for row in rows]

    def list_by_status(self, status: OpportunityStatus) -> List[Opportunity]:
        """List opportunities by status."""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM opportunities WHERE status = ? ORDER BY cfp_deadline ASC",
                (status.value,)
            ).fetchall()
            return [Opportunity.from_dict(dict(row)) for row in rows]

    def list_by_source(self, source: str) -> List[Opportunity]:
        """List opportunities by source adapter."""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM opportunities WHERE source = ? ORDER BY cfp_deadline ASC",
                (source,)
            ).fetchall()
            return [Opportunity.from_dict(dict(row)) for row in rows]

    def list_upcoming(self, days: int = 30) -> List[Opportunity]:
        """List opportunities with deadlines in the next N days."""
        now = datetime.utcnow()
        cutoff = datetime(now.year, now.month, now.day)

        with self._get_conn() as conn:
            rows = conn.execute("""
                SELECT * FROM opportunities
                WHERE (
                    (cfp_deadline IS NOT NULL AND cfp_deadline >= ?)
                    OR (application_deadline IS NOT NULL AND application_deadline >= ?)
                    OR (event_start IS NOT NULL AND event_start >= ?)
                )
                AND status != 'expired'
                ORDER BY COALESCE(cfp_deadline, application_deadline, event_start) ASC
            """, (cutoff.isoformat(), cutoff.isoformat(), cutoff.isoformat())).fetchall()

            results = []
            for row in rows:
                opp = Opportunity.from_dict(dict(row))
                deadline = opp.get_primary_deadline()
                if deadline:
                    delta = deadline - now
                    if 0 <= delta.days <= days:
                        results.append(opp)
                else:
                    results.append(opp)
            return results

    def list_by_rag_status(self, rag_status: RAGStatus) -> List[Opportunity]:
        """List opportunities by RAG status."""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM opportunities WHERE rag_status = ? ORDER BY cfp_deadline ASC",
                (rag_status.value,)
            ).fetchall()
            return [Opportunity.from_dict(dict(row)) for row in rows]

    def list_active(self) -> List[Opportunity]:
        """List non-expired opportunities that need tracking."""
        with self._get_conn() as conn:
            rows = conn.execute("""
                SELECT * FROM opportunities
                WHERE status NOT IN ('expired', 'submitted')
                ORDER BY COALESCE(cfp_deadline, application_deadline, event_start) ASC
            """).fetchall()
            return [Opportunity.from_dict(dict(row)) for row in rows]

    def update_all_rag_statuses(self) -> int:
        """Update RAG status for all active opportunities. Returns count updated."""
        active = self.list_active()
        count = 0
        for opp in active:
            old_status = opp.rag_status
            opp.update_rag_status()
            if opp.rag_status != old_status:
                self.update(opp)
                count += 1
        return count

    def mark_expired(self) -> int:
        """Mark past-deadline opportunities as expired. Returns count updated."""
        now = datetime.utcnow().isoformat()
        with self._get_conn() as conn:
            cursor = conn.execute("""
                UPDATE opportunities
                SET status = 'expired', updated_at = ?
                WHERE status NOT IN ('expired', 'submitted')
                AND (
                    (cfp_deadline IS NOT NULL AND cfp_deadline < ?)
                    OR (application_deadline IS NOT NULL AND application_deadline < ?)
                )
                AND event_end IS NOT NULL AND event_end < ?
            """, (now, now, now, now))
            conn.commit()
            return cursor.rowcount

    def count(self) -> dict:
        """Get count statistics."""
        with self._get_conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM opportunities").fetchone()[0]
            by_status = {}
            for status in OpportunityStatus:
                count = conn.execute(
                    "SELECT COUNT(*) FROM opportunities WHERE status = ?",
                    (status.value,)
                ).fetchone()[0]
                by_status[status.value] = count
            by_rag = {}
            for rag in RAGStatus:
                count = conn.execute(
                    "SELECT COUNT(*) FROM opportunities WHERE rag_status = ?",
                    (rag.value,)
                ).fetchone()[0]
                by_rag[rag.value] = count
            return {
                "total": total,
                "by_status": by_status,
                "by_rag": by_rag,
            }
