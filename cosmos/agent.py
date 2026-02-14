"""
Cosmos Reason 2 connector agent — NVIDIA Cosmos Cookoff 2026 entry stub.

This module provides the CosmosAgent class that bridges FactoryLM's
PLC fault/anomaly events to NVIDIA Cosmos Reason 2 for root-cause
analysis and video-grounded reasoning.

Read-only — CosmosAgent never writes to PLCs.
"""

import asyncio
import datetime
import json
import logging
import os
import sqlite3
from pathlib import Path

from cosmos.client import CosmosClient
from cosmos.models import CosmosInsight

logger = logging.getLogger(__name__)


class CosmosAgent:
    """Connector between FactoryLM incidents and NVIDIA Cosmos Reason 2."""

    def __init__(self, config_path: str | None = None) -> None:
        cfg_file = Path(config_path) if config_path else Path("config/cosmos.yaml")
        self.enabled: bool = False
        self.api_key: str = os.getenv("NVIDIA_COSMOS_API_KEY", "")
        self._config: dict = {}
        self.client = CosmosClient(config_path=config_path)

        if cfg_file.exists():
            try:
                import yaml  # optional dependency

                with cfg_file.open("r", encoding="utf-8") as f:
                    raw = yaml.safe_load(f) or {}
                self._config = raw.get("cosmos", {})
                self.enabled = bool(self._config.get("enabled", False))
            except ImportError:
                logger.warning(
                    "PyYAML not installed — falling back to defaults. "
                    "Install pyyaml to load %s",
                    cfg_file,
                )
            except Exception:
                logger.exception("Failed to load Cosmos config from %s", cfg_file)
        else:
            logger.info("Cosmos config not found at %s — using defaults", cfg_file)

    async def on_incident(
        self,
        incident_id: str,
        node_id: str,
        tags: dict,
        video_url: str = "",
    ) -> CosmosInsight:
        """Analyse an incident via Cosmos Reason 2.

        Returns a CosmosInsight with root-cause analysis.
        """
        logger.info(
            "Cosmos analysis requested for incident=%s node=%s",
            incident_id,
            node_id,
        )

        return self.client.analyze_incident(
            incident_id=incident_id,
            node_id=node_id,
            tags=tags,
            video_url=video_url,
        )

    async def fetch_tag_history(self, node_id: str, seconds: int = 60) -> dict:
        """Return recent tag values for *node_id*.

        Returns an empty dict until the Matrix Postgres API integration is
        wired up.
        """
        # TODO: Fetch from Matrix Postgres API
        return {}

    def is_enabled(self) -> bool:
        """Return True when Cosmos integration is both configured and keyed."""
        return self.enabled and bool(self.api_key)

    # ------------------------------------------------------------------
    # Incident watching
    # ------------------------------------------------------------------

    async def watch_for_incidents(
        self,
        db_path: str = "sim/tags.db",
        poll_interval: float = 2.0,
    ) -> None:
        """Poll *tag_snapshots* for new faults and analyse them via Cosmos.

        Runs indefinitely until interrupted with ``KeyboardInterrupt``.
        """
        path = Path(db_path)
        self._ensure_insights_table(path)
        last_seen_id: int = 0

        logger.info(
            "Watching for incidents in %s (poll every %.1fs)", path, poll_interval
        )

        try:
            while True:
                conn = sqlite3.connect(str(path))
                conn.row_factory = sqlite3.Row
                try:
                    rows = conn.execute(
                        "SELECT * FROM tag_snapshots "
                        "WHERE fault_alarm = 1 AND id > ? "
                        "ORDER BY id ASC",
                        (last_seen_id,),
                    ).fetchall()
                finally:
                    conn.close()

                for row in rows:
                    row_dict = dict(row)
                    last_seen_id = row_dict["id"]
                    incident_id = f"fault-{row_dict['id']}"
                    node_id = row_dict.get("node_id", "unknown")
                    tags = {
                        k: v
                        for k, v in row_dict.items()
                        if k not in ("id", "node_id")
                    }

                    insight = await self.on_incident(
                        incident_id=incident_id,
                        node_id=node_id,
                        tags=tags,
                    )
                    self._store_insight(path, insight)
                    logger.info(
                        "Insight stored: incident=%s confidence=%.2f summary=%s",
                        insight.incident_id,
                        insight.confidence,
                        insight.summary,
                    )

                await asyncio.sleep(poll_interval)
        except KeyboardInterrupt:
            logger.info("Incident watcher stopped by user")

    def _ensure_insights_table(self, db_path: Path) -> None:
        """Create the *cosmos_insights* table if it does not exist."""
        conn = sqlite3.connect(str(db_path))
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cosmos_insights (
                    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
                    incident_id           TEXT NOT NULL,
                    node_id               TEXT NOT NULL,
                    timestamp             TEXT NOT NULL,
                    summary               TEXT,
                    root_cause            TEXT,
                    confidence            REAL,
                    reasoning             TEXT,
                    suggested_checks_json TEXT,
                    video_url             TEXT,
                    cosmos_model          TEXT
                )
                """
            )
            conn.commit()
        finally:
            conn.close()

    def _store_insight(self, db_path: Path, insight: CosmosInsight) -> None:
        """Insert a *CosmosInsight* into the *cosmos_insights* table."""
        conn = sqlite3.connect(str(db_path))
        try:
            conn.execute(
                """
                INSERT INTO cosmos_insights (
                    incident_id, node_id, timestamp, summary, root_cause,
                    confidence, reasoning, suggested_checks_json, video_url,
                    cosmos_model
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    insight.incident_id,
                    insight.node_id,
                    insight.timestamp.isoformat(),
                    insight.summary,
                    insight.root_cause,
                    insight.confidence,
                    insight.reasoning,
                    json.dumps(insight.suggested_checks),
                    insight.video_url,
                    insight.cosmos_model,
                ),
            )
            conn.commit()
        finally:
            conn.close()
