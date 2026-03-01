"""Core async orchestrator — runs incident watcher + twin comparator loops."""

import asyncio
import logging
from functools import partial

import httpx

from cosmos.client import CosmosClient
from cosmos.models import CosmosInsight
from services.plc_monitor.config import MonitorConfig
from services.plc_monitor.twin_comparator import TwinComparator, TwinReader
from services.plc_monitor.telegram_alerter import TelegramAlerter

logger = logging.getLogger(__name__)


class PLCMonitor:
    """Manages two concurrent async loops: incident watcher + twin comparator."""

    def __init__(self, config: MonitorConfig) -> None:
        self.config = config
        self.cosmos = CosmosClient(config_path="config/cosmos.yaml")
        self.alerter = TelegramAlerter(config.telegram_bot_token, config.telegram_chat_id)
        self.twin_reader = TwinReader(config.factoryio_host, config.factoryio_port)
        self.twin_comparator = TwinComparator(threshold=config.twin_divergence_threshold)
        self._http = httpx.AsyncClient(timeout=10.0)
        self._seen_incident_ids: set[int] = set()
        self._running = False

        # Stats
        self.incidents_processed = 0
        self.twin_comparisons = 0
        self.divergences_detected = 0
        self.alerts_sent = 0

    async def start(self) -> None:
        """Launch both loops as concurrent tasks."""
        self._running = True
        logger.info(
            "PLCMonitor starting — matrix=%s, twin=%s:%d, poll=%.1fs, twin_interval=%.1fs",
            self.config.matrix_url,
            self.config.factoryio_host,
            self.config.factoryio_port,
            self.config.poll_interval,
            self.config.twin_compare_interval,
        )
        await asyncio.gather(
            self._incident_loop(),
            self._twin_loop(),
        )

    async def stop(self) -> None:
        """Signal both loops to stop."""
        self._running = False
        self.twin_reader.disconnect()
        await self.alerter.close()
        await self._http.aclose()
        logger.info("PLCMonitor stopped")

    # ------------------------------------------------------------------
    # Loop 1: Incident watcher
    # ------------------------------------------------------------------

    async def _incident_loop(self) -> None:
        """Poll Matrix API for open incidents, analyze with Cosmos, alert."""
        logger.info("Incident watcher loop started (every %.1fs)", self.config.poll_interval)
        consecutive_failures = 0
        while self._running:
            try:
                await self._check_incidents()
                consecutive_failures = 0
            except (httpx.ConnectError, httpx.ConnectTimeout):
                consecutive_failures += 1
                backoff = min(self.config.poll_interval * (2 ** consecutive_failures), 300)
                logger.warning(
                    "Matrix unreachable, retry in %ds (%d consecutive failures)",
                    backoff, consecutive_failures,
                )
                await asyncio.sleep(backoff)
                continue
            except Exception:
                logger.exception("Incident loop error")
            await asyncio.sleep(self.config.poll_interval)

    async def _check_incidents(self) -> None:
        """Fetch open incidents from Matrix API and process new ones."""
        url = f"{self.config.matrix_url}/api/incidents"
        try:
            resp = await self._http.get(url, params={"status": "open"})
            resp.raise_for_status()
        except (httpx.ConnectError, httpx.ConnectTimeout):
            raise  # propagate to loop for backoff handling
        except httpx.HTTPStatusError as e:
            logger.warning("Matrix API error: %s", e)
            return

        incidents = resp.json()
        if not isinstance(incidents, list):
            incidents = incidents.get("incidents", [])

        for incident in incidents:
            inc_id = incident.get("id")
            if inc_id is None or inc_id in self._seen_incident_ids:
                continue
            self._seen_incident_ids.add(inc_id)

            logger.info("New incident #%s — analyzing with Cosmos", inc_id)
            self.incidents_processed += 1

            # Run synchronous Cosmos analysis in executor
            loop = asyncio.get_running_loop()
            insight = await loop.run_in_executor(
                None,
                partial(
                    self.cosmos.analyze_incident,
                    incident_id=str(inc_id),
                    node_id=incident.get("node_id", "unknown"),
                    tags=incident.get("tags", {}),
                ),
            )

            # Post insight back to Matrix API
            await self._post_insight(insight)

            # Send Telegram alert
            if self.alerter.enabled:
                sent = await self.alerter.send_incident_alert(incident, insight)
                if sent:
                    self.alerts_sent += 1

    async def _post_insight(self, insight: CosmosInsight) -> None:
        """POST a CosmosInsight back to Matrix API."""
        url = f"{self.config.matrix_url}/api/insights"
        payload = {
            "incident_id": insight.incident_id,
            "node_id": insight.node_id,
            "summary": insight.summary,
            "root_cause": insight.root_cause,
            "confidence": insight.confidence,
            "reasoning": insight.reasoning,
            "suggested_checks": insight.suggested_checks,
            "cosmos_model": insight.cosmos_model,
        }
        try:
            resp = await self._http.post(url, json=payload)
            resp.raise_for_status()
            logger.info("Insight posted for incident %s", insight.incident_id)
        except Exception as e:
            logger.warning("Failed to post insight: %s", e)

    # ------------------------------------------------------------------
    # Loop 2: Twin comparator
    # ------------------------------------------------------------------

    async def _twin_loop(self) -> None:
        """Compare real PLC tags (from Matrix API) vs Factory I/O sim tags."""
        logger.info(
            "Twin comparator loop started (every %.1fs, threshold=%.0f%%)",
            self.config.twin_compare_interval,
            self.config.twin_divergence_threshold * 100,
        )
        consecutive_failures = 0
        while self._running:
            try:
                await self._compare_twins()
                consecutive_failures = 0
            except (httpx.ConnectError, httpx.ConnectTimeout):
                consecutive_failures += 1
                backoff = min(self.config.twin_compare_interval * (2 ** consecutive_failures), 300)
                logger.warning(
                    "Matrix unreachable (twin), retry in %ds (%d consecutive failures)",
                    backoff, consecutive_failures,
                )
                await asyncio.sleep(backoff)
                continue
            except Exception:
                logger.exception("Twin loop error")
            await asyncio.sleep(self.config.twin_compare_interval)

    async def _compare_twins(self) -> None:
        """Fetch real tags from Matrix, sim tags from Factory I/O, compare."""
        # Fetch latest real tags from Matrix API
        url = f"{self.config.matrix_url}/api/tags"
        try:
            resp = await self._http.get(url, params={"limit": 1})
            resp.raise_for_status()
        except (httpx.ConnectError, httpx.ConnectTimeout):
            raise  # propagate to loop for backoff handling
        except httpx.HTTPStatusError as e:
            logger.warning("Matrix API tags error: %s", e)
            return

        data = resp.json()
        if isinstance(data, list):
            real_tags = data[0] if data else {}
        elif isinstance(data, dict) and "tags" in data:
            tags_list = data["tags"]
            real_tags = tags_list[0] if tags_list else {}
        else:
            real_tags = data

        if not real_tags:
            logger.debug("No real tags available for twin compare")
            return

        # Read sim tags from Factory I/O via Modbus
        loop = asyncio.get_running_loop()
        sim_tags = await loop.run_in_executor(None, self.twin_reader.read_tags)

        if sim_tags is None:
            logger.debug("Factory I/O not reachable for twin compare")
            return

        self.twin_comparisons += 1

        # Compare
        diff = self.twin_comparator.compare(real_tags, sim_tags)
        logger.debug(
            "Twin compare #%d: drift=%.3f diverged=%s mismatches=%d",
            self.twin_comparisons, diff.drift_score, diff.diverged, len(diff.mismatches),
        )

        if not diff.diverged:
            return

        self.divergences_detected += 1
        logger.warning("Twin divergence detected: %s", diff.summary)

        # Analyze divergence with Cosmos
        context = (
            f"Digital twin divergence detected. Drift score: {diff.drift_score:.2f}. "
            f"Mismatches: {diff.summary}"
        )
        insight = await loop.run_in_executor(
            None,
            partial(
                self.cosmos.analyze_incident,
                incident_id=f"twin-divergence-{self.divergences_detected}",
                node_id="twin-comparator",
                tags=real_tags,
                context=context,
            ),
        )

        # Post insight to Matrix API
        await self._post_insight(insight)

        # Send Telegram divergence alert
        if self.alerter.enabled:
            sent = await self.alerter.send_divergence_alert(
                drift_score=diff.drift_score,
                mismatches=diff.mismatches,
                insight=insight,
            )
            if sent:
                self.alerts_sent += 1

    def get_stats(self) -> dict:
        """Return current monitor stats for health endpoint."""
        return {
            "incidents_processed": self.incidents_processed,
            "twin_comparisons": self.twin_comparisons,
            "divergences_detected": self.divergences_detected,
            "alerts_sent": self.alerts_sent,
            "seen_incident_ids": len(self._seen_incident_ids),
            "twin_reader_connected": self.twin_reader.connected,
            "cosmos_available": self.cosmos.is_available(),
            "telegram_enabled": self.alerter.enabled,
        }
