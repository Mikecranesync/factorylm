"""SQLite persistence for the autonomous scene learner.

Stores scenes, I/O points (with official docs + learned descriptions),
experiments, learnings, and sequences. All data lives in data/learner/knowledge.db.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

logger = logging.getLogger("factorylm.learner.knowledge_store")

REPO_ROOT = Path(__file__).parent.parent.parent
DEFAULT_DB_PATH = REPO_ROOT / "data" / "learner" / "knowledge.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS scenes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    discovered_at TEXT NOT NULL DEFAULT (datetime('now')),
    description TEXT,
    io_count INTEGER DEFAULT 0,
    program_source TEXT
);

CREATE TABLE IF NOT EXISTS io_points (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scene_id INTEGER NOT NULL REFERENCES scenes(id),
    io_type TEXT NOT NULL,           -- coil | discrete_input | register
    address INTEGER NOT NULL,
    name TEXT NOT NULL,
    data_type TEXT DEFAULT 'BOOL',   -- BOOL | INT | REAL
    official_description TEXT,        -- from PLC program template
    learned_description TEXT,         -- from Cosmos R2 experiments
    kb_prior_knowledge TEXT,          -- from Mem0 search before experiments
    verified INTEGER DEFAULT 0,       -- 1=observed matches official, 0=untested
    mismatch_note TEXT,               -- if verified but doesn't match
    confidence REAL DEFAULT 0.0,
    test_count INTEGER DEFAULT 0,
    UNIQUE(scene_id, io_type, address)
);

CREATE TABLE IF NOT EXISTS experiments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scene_id INTEGER NOT NULL REFERENCES scenes(id),
    experiment_type TEXT NOT NULL,     -- SingleCoilToggle | RegisterSweep | etc.
    actions_json TEXT,                 -- JSON: what was done
    before_tags_json TEXT,             -- JSON: tag snapshot before
    after_tags_json TEXT,              -- JSON: tag snapshot after
    before_screenshot TEXT,            -- file path
    after_screenshot TEXT,             -- file path
    vision_before TEXT,                -- R2 description of before
    vision_after TEXT,                 -- R2 description of after
    vision_delta TEXT,                 -- R2 description of change
    tag_delta_json TEXT,               -- JSON: which tags changed
    learning TEXT,                     -- one-sentence learning
    verified_against_docs INTEGER DEFAULT 0,  -- 1=matches official docs
    started_at TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS learnings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scene_id INTEGER NOT NULL REFERENCES scenes(id),
    io_point_id INTEGER REFERENCES io_points(id),
    experiment_id INTEGER REFERENCES experiments(id),
    category TEXT,                     -- behavior | interaction | sequence | edge_case
    summary TEXT NOT NULL,
    confidence REAL DEFAULT 0.5,
    kb_written INTEGER DEFAULT 0,      -- 1=written to Mem0 KB
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sequences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scene_id INTEGER NOT NULL REFERENCES scenes(id),
    name TEXT NOT NULL,
    steps_json TEXT NOT NULL,           -- JSON array of step dicts
    success_rate REAL DEFAULT 0.0,
    tested_count INTEGER DEFAULT 0
);
"""


@dataclass
class IOPoint:
    """A single I/O point parsed from a PLC program."""
    tag_name: str
    address: int
    io_type: str        # coil | discrete_input | register
    data_type: str      # BOOL | INT | REAL
    description: str
    scene_name: str


class KnowledgeStore:
    """SQLite-backed persistence for scene learner data."""

    def __init__(self, db_path: Optional[str | Path] = None):
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._init_schema()

    def _init_schema(self):
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def close(self):
        self._conn.close()

    # --- Scenes ---

    def add_scene(self, name: str, description: str = "",
                  program_source: str = "") -> int:
        """Insert or get a scene. Returns scene_id."""
        row = self._conn.execute(
            "SELECT id FROM scenes WHERE name = ?", (name,)
        ).fetchone()
        if row:
            return row["id"]
        cur = self._conn.execute(
            "INSERT INTO scenes (name, description, program_source) VALUES (?, ?, ?)",
            (name, description, program_source),
        )
        self._conn.commit()
        return cur.lastrowid

    def get_scene(self, scene_id: int) -> Optional[dict]:
        row = self._conn.execute(
            "SELECT * FROM scenes WHERE id = ?", (scene_id,)
        ).fetchone()
        return dict(row) if row else None

    # --- I/O Points ---

    def add_io_point(self, scene_id: int, io_point: IOPoint) -> int:
        """Insert or update an I/O point. Returns io_point_id."""
        row = self._conn.execute(
            "SELECT id FROM io_points WHERE scene_id = ? AND io_type = ? AND address = ?",
            (scene_id, io_point.io_type, io_point.address),
        ).fetchone()
        if row:
            self._conn.execute(
                """UPDATE io_points SET name = ?, data_type = ?, official_description = ?
                   WHERE id = ?""",
                (io_point.tag_name, io_point.data_type, io_point.description, row["id"]),
            )
            self._conn.commit()
            return row["id"]
        cur = self._conn.execute(
            """INSERT INTO io_points
               (scene_id, io_type, address, name, data_type, official_description)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (scene_id, io_point.io_type, io_point.address,
             io_point.tag_name, io_point.data_type, io_point.description),
        )
        self._conn.commit()
        return cur.lastrowid

    def bulk_add_io_points(self, scene_id: int, io_points: list[IOPoint]) -> list[int]:
        """Add multiple I/O points. Returns list of io_point_ids."""
        ids = []
        for pt in io_points:
            ids.append(self.add_io_point(scene_id, pt))
        # Update scene io_count
        self._conn.execute(
            "UPDATE scenes SET io_count = ? WHERE id = ?",
            (len(io_points), scene_id),
        )
        self._conn.commit()
        return ids

    def get_io_points(self, scene_id: int) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM io_points WHERE scene_id = ? ORDER BY io_type, address",
            (scene_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_untested_io(self, scene_id: int) -> list[dict]:
        """I/O points with zero experiments."""
        rows = self._conn.execute(
            "SELECT * FROM io_points WHERE scene_id = ? AND test_count = 0 ORDER BY io_type, address",
            (scene_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_low_confidence_io(self, scene_id: int, threshold: float = 0.5) -> list[dict]:
        """I/O points below confidence threshold."""
        rows = self._conn.execute(
            """SELECT * FROM io_points
               WHERE scene_id = ? AND confidence < ? AND test_count > 0
               ORDER BY confidence ASC""",
            (scene_id, threshold),
        ).fetchall()
        return [dict(r) for r in rows]

    def update_io_learning(self, io_point_id: int, learned_description: str,
                           confidence: float, verified: bool = False,
                           mismatch_note: str = "") -> None:
        """Update an I/O point with experiment results."""
        self._conn.execute(
            """UPDATE io_points
               SET learned_description = ?, confidence = ?, verified = ?,
                   mismatch_note = ?, test_count = test_count + 1
               WHERE id = ?""",
            (learned_description, confidence, int(verified), mismatch_note, io_point_id),
        )
        self._conn.commit()

    def set_kb_prior(self, io_point_id: int, kb_text: str) -> None:
        """Store KB prior knowledge for an I/O point."""
        self._conn.execute(
            "UPDATE io_points SET kb_prior_knowledge = ? WHERE id = ?",
            (kb_text, io_point_id),
        )
        self._conn.commit()

    # --- Experiments ---

    def start_experiment(self, scene_id: int, experiment_type: str,
                         actions: dict) -> int:
        """Create a new experiment record. Returns experiment_id."""
        cur = self._conn.execute(
            """INSERT INTO experiments (scene_id, experiment_type, actions_json)
               VALUES (?, ?, ?)""",
            (scene_id, experiment_type, json.dumps(actions)),
        )
        self._conn.commit()
        return cur.lastrowid

    def record_before(self, experiment_id: int, tags: dict,
                      screenshot_path: str = "", vision_text: str = "") -> None:
        self._conn.execute(
            """UPDATE experiments
               SET before_tags_json = ?, before_screenshot = ?, vision_before = ?
               WHERE id = ?""",
            (json.dumps(tags), screenshot_path, vision_text, experiment_id),
        )
        self._conn.commit()

    def record_after(self, experiment_id: int, tags: dict,
                     screenshot_path: str = "", vision_text: str = "") -> None:
        self._conn.execute(
            """UPDATE experiments
               SET after_tags_json = ?, after_screenshot = ?, vision_after = ?
               WHERE id = ?""",
            (json.dumps(tags), screenshot_path, vision_text, experiment_id),
        )
        self._conn.commit()

    def complete_experiment(self, experiment_id: int, tag_delta: dict,
                            vision_delta: str, learning: str,
                            verified: bool = False) -> None:
        self._conn.execute(
            """UPDATE experiments
               SET tag_delta_json = ?, vision_delta = ?, learning = ?,
                   verified_against_docs = ?, completed_at = datetime('now')
               WHERE id = ?""",
            (json.dumps(tag_delta), vision_delta, learning,
             int(verified), experiment_id),
        )
        self._conn.commit()

    def get_experiments(self, scene_id: int) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM experiments WHERE scene_id = ? ORDER BY started_at",
            (scene_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    # --- Learnings ---

    def add_learning(self, scene_id: int, summary: str,
                     confidence: float = 0.5, category: str = "behavior",
                     io_point_id: Optional[int] = None,
                     experiment_id: Optional[int] = None) -> int:
        cur = self._conn.execute(
            """INSERT INTO learnings
               (scene_id, io_point_id, experiment_id, category, summary, confidence)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (scene_id, io_point_id, experiment_id, category, summary, confidence),
        )
        self._conn.commit()
        return cur.lastrowid

    def mark_kb_written(self, learning_id: int) -> None:
        self._conn.execute(
            "UPDATE learnings SET kb_written = 1 WHERE id = ?",
            (learning_id,),
        )
        self._conn.commit()

    def get_unwritten_learnings(self, scene_id: int) -> list[dict]:
        """Learnings not yet written to KB."""
        rows = self._conn.execute(
            "SELECT * FROM learnings WHERE scene_id = ? AND kb_written = 0",
            (scene_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    # --- Sequences ---

    def add_sequence(self, scene_id: int, name: str, steps: list[dict]) -> int:
        cur = self._conn.execute(
            "INSERT INTO sequences (scene_id, name, steps_json) VALUES (?, ?, ?)",
            (scene_id, name, json.dumps(steps)),
        )
        self._conn.commit()
        return cur.lastrowid

    # --- Prompt Context ---

    def to_prompt_context(self, scene_id: int) -> str:
        """Format all learnings as a context string for LLM prompts."""
        scene = self.get_scene(scene_id)
        if not scene:
            return ""

        lines = [f"Scene: {scene['name']}"]
        if scene.get("description"):
            lines.append(f"Description: {scene['description']}")
        lines.append("")

        io_pts = self.get_io_points(scene_id)
        if io_pts:
            lines.append("I/O Points:")
            for pt in io_pts:
                status = "VERIFIED" if pt["verified"] else (
                    f"confidence={pt['confidence']:.1f}" if pt["test_count"] > 0 else "UNTESTED"
                )
                desc = pt.get("learned_description") or pt.get("official_description") or "unknown"
                lines.append(f"  {pt['io_type']} {pt['address']} ({pt['name']}): {desc} [{status}]")
                if pt.get("mismatch_note"):
                    lines.append(f"    MISMATCH: {pt['mismatch_note']}")
            lines.append("")

        learnings = self._conn.execute(
            "SELECT * FROM learnings WHERE scene_id = ? ORDER BY confidence DESC",
            (scene_id,),
        ).fetchall()
        if learnings:
            lines.append("Learnings:")
            for l in learnings:
                lines.append(f"  [{l['category']}] {l['summary']} (conf={l['confidence']:.1f})")

        return "\n".join(lines)

    # --- Export ---

    def export_scene_knowledge(self, scene_id: int) -> dict:
        """Full JSON-serializable dump of a scene's knowledge."""
        scene = self.get_scene(scene_id)
        if not scene:
            return {"error": f"Scene {scene_id} not found"}

        io_pts = self.get_io_points(scene_id)
        experiments = self.get_experiments(scene_id)
        learnings = self._conn.execute(
            "SELECT * FROM learnings WHERE scene_id = ?", (scene_id,)
        ).fetchall()
        sequences = self._conn.execute(
            "SELECT * FROM sequences WHERE scene_id = ?", (scene_id,)
        ).fetchall()

        return {
            "scene": scene,
            "io_points": io_pts,
            "experiments": experiments,
            "learnings": [dict(l) for l in learnings],
            "sequences": [dict(s) for s in sequences],
            "stats": {
                "total_io": len(io_pts),
                "tested_io": sum(1 for p in io_pts if p["test_count"] > 0),
                "verified_io": sum(1 for p in io_pts if p["verified"]),
                "total_experiments": len(experiments),
                "total_learnings": len(learnings),
                "avg_confidence": (
                    sum(p["confidence"] for p in io_pts) / len(io_pts)
                    if io_pts else 0.0
                ),
            },
        }
