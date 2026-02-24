"""SQLite tag store — schema extracted from Matrix API."""

from __future__ import annotations

import datetime
import json
import sqlite3
from pathlib import Path
from typing import Any


class TagStore:
    """Thin wrapper around SQLite for PLC tag snapshots and incidents."""

    def __init__(self, db_path: str = "~/.factorylm/tags.db") -> None:
        resolved = Path(db_path).expanduser()
        resolved.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = str(resolved)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self) -> None:
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS tag_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                node_id TEXT NOT NULL DEFAULT 'local',
                tags_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS incidents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                node_id TEXT NOT NULL DEFAULT 'local',
                error_code INTEGER,
                error_message TEXT,
                status TEXT DEFAULT 'open',
                trigger_tag_id INTEGER,
                tags_json TEXT
            );
            CREATE TABLE IF NOT EXISTS cosmos_insights (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                incident_id INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                summary TEXT,
                root_cause TEXT,
                confidence REAL,
                reasoning TEXT,
                suggested_checks_json TEXT,
                cosmos_model TEXT,
                FOREIGN KEY (incident_id) REFERENCES incidents(id)
            );
        """)
        conn.commit()
        conn.close()

    def insert_tags(self, tags: dict[str, Any], node_id: str = "local") -> int:
        """Insert a tag snapshot. Returns the row ID."""
        conn = self._get_conn()
        try:
            ts = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
            cur = conn.execute(
                "INSERT INTO tag_snapshots (timestamp, node_id, tags_json) VALUES (?,?,?)",
                (ts, node_id, json.dumps(tags)),
            )

            tag_id = cur.lastrowid

            # Auto-create incident on fault_alarm or e_stop
            fault = tags.get("fault_alarm", False)
            e_stop = tags.get("e_stop", False)
            error_code = tags.get("error_code", 0)

            if fault or e_stop:
                effective_error = error_code if error_code else (-1 if e_stop else 0)
                existing = conn.execute(
                    "SELECT id FROM incidents WHERE node_id=? AND error_code=? AND status='open'",
                    (node_id, effective_error),
                ).fetchone()
                if not existing:
                    err_msg = tags.get("error_message", "")
                    if not err_msg and e_stop:
                        err_msg = "Emergency stop activated"
                    conn.execute(
                        """INSERT INTO incidents
                           (timestamp, node_id, error_code, error_message, status, trigger_tag_id, tags_json)
                           VALUES (?,?,?,?,?,?,?)""",
                        (ts, node_id, effective_error, err_msg, "open", tag_id, json.dumps(tags)),
                    )

            conn.commit()
            return tag_id
        finally:
            conn.close()

    def get_latest(self, limit: int = 1) -> list[dict]:
        """Return the N most recent tag snapshots."""
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM tag_snapshots ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
            results = []
            for r in rows:
                d = dict(r)
                d["tags"] = json.loads(d.pop("tags_json"))
                results.append(d)
            return results
        finally:
            conn.close()

    def get_latest_tags(self) -> dict[str, Any] | None:
        """Return just the tag dict from the most recent snapshot, or None."""
        rows = self.get_latest(1)
        if rows:
            return rows[0].get("tags", {})
        return None

    def get_incidents(self, status: str | None = None, limit: int = 50) -> list[dict]:
        """Return incidents, optionally filtered by status."""
        conn = self._get_conn()
        try:
            if status:
                rows = conn.execute(
                    "SELECT * FROM incidents WHERE status=? ORDER BY id DESC LIMIT ?",
                    (status, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM incidents ORDER BY id DESC LIMIT ?", (limit,)
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def insert_insight(self, incident_id: int, summary: str, root_cause: str,
                       confidence: float, reasoning: str, suggested_checks: list[str],
                       cosmos_model: str = "") -> int:
        """Insert a cosmos insight and mark incident as analyzed."""
        conn = self._get_conn()
        try:
            ts = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
            cur = conn.execute(
                """INSERT INTO cosmos_insights
                   (incident_id, timestamp, summary, root_cause, confidence,
                    reasoning, suggested_checks_json, cosmos_model)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (incident_id, ts, summary, root_cause, confidence,
                 reasoning, json.dumps(suggested_checks), cosmos_model),
            )
            conn.execute(
                "UPDATE incidents SET status='analyzed' WHERE id=?", (incident_id,)
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    def get_snapshots_as_flat(self, limit: int = 50) -> list[dict]:
        """Return snapshots with tags flattened into top-level keys (for API compat)."""
        rows = self.get_latest(limit)
        flat = []
        for r in rows:
            entry = {"id": r["id"], "timestamp": r["timestamp"], "node_id": r["node_id"]}
            entry.update(r.get("tags", {}))
            flat.append(entry)
        return flat
