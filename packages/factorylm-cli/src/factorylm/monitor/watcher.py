"""Fault detection watcher — monitors TagStore for fault/e-stop transitions.

Simplified extraction from services/plc_monitor/monitor.py.
Optionally calls Cosmos for analysis on new incidents.
"""

from __future__ import annotations

import asyncio
import logging
from functools import partial
from typing import Any

from factorylm.cosmos.client import CosmosClient
from factorylm.db.store import TagStore

logger = logging.getLogger(__name__)


class FaultWatcher:
    """Watches the local TagStore for new open incidents and analyzes them."""

    def __init__(
        self,
        store: TagStore,
        cosmos: CosmosClient | None = None,
        poll_interval: float = 5.0,
    ) -> None:
        self.store = store
        self.cosmos = cosmos or CosmosClient()
        self.poll_interval = poll_interval
        self._seen_ids: set[int] = set()
        self._running = False
        self.incidents_processed = 0

    async def run(self) -> None:
        """Main loop — poll for new open incidents."""
        self._running = True
        logger.info("FaultWatcher started (poll=%.1fs)", self.poll_interval)

        while self._running:
            try:
                await self._check()
            except Exception:
                logger.exception("FaultWatcher error")
            await asyncio.sleep(self.poll_interval)

    async def stop(self) -> None:
        self._running = False

    async def _check(self) -> None:
        incidents = self.store.get_incidents(status="open", limit=20)
        for inc in incidents:
            inc_id = inc.get("id")
            if inc_id is None or inc_id in self._seen_ids:
                continue
            self._seen_ids.add(inc_id)
            self.incidents_processed += 1
            logger.info("New incident #%s — analyzing", inc_id)

            tags = {}
            if inc.get("tags_json"):
                import json
                try:
                    tags = json.loads(inc["tags_json"])
                except (json.JSONDecodeError, TypeError):
                    pass

            loop = asyncio.get_running_loop()
            insight = await loop.run_in_executor(
                None,
                partial(
                    self.cosmos.analyze_incident,
                    incident_id=str(inc_id),
                    node_id=inc.get("node_id", "local"),
                    tags=tags,
                ),
            )

            self.store.insert_insight(
                incident_id=inc_id,
                summary=insight.summary,
                root_cause=insight.root_cause,
                confidence=insight.confidence,
                reasoning=insight.reasoning,
                suggested_checks=insight.suggested_checks,
                cosmos_model=insight.cosmos_model,
            )
            logger.info("Insight stored for incident #%s", inc_id)
