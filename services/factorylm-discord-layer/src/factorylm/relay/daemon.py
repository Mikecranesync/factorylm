"""Async relay daemon — aiohttp server for agent webhook posting.

Extracted from packages/factorylm-cli/discord/relay.py AgentRelay pattern.
Accepts POST /relay with {agent, message, format}, looks up the agent's
webhook URL from config, and queues the message for delivery.
"""

from __future__ import annotations

import asyncio
import datetime
import logging
import signal
import time
from typing import Any

import aiohttp
from aiohttp import web

from factorylm.config import get_all_instances
from factorylm.models import FactoryLMConfig
from factorylm.relay.rate_limiter import WebhookRateLimiter

logger = logging.getLogger(__name__)


class AsyncRelayDaemon:
    """HTTP relay server that posts agent messages to Discord webhooks.

    Extracted from AgentRelay._send_webhook() pattern in factorylm-cli.
    """

    def __init__(self, config: FactoryLMConfig) -> None:
        self.config = config
        self._app = web.Application()
        self._app.router.add_post("/relay", self._handle_relay)
        self._app.router.add_get("/status", self._handle_status)
        self._app.router.add_get("/health", self._handle_health)
        self._session: aiohttp.ClientSession | None = None
        self._start_time = time.monotonic()
        self._message_count = 0
        self._queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=500)
        self._drain_task: asyncio.Task | None = None
        self._shutting_down = False
        self._last_heartbeat: float | None = None  # Timestamp of last successful message relay
        self.rate_limiter = WebhookRateLimiter(max_queue_size=500)

    @property
    def app(self) -> web.Application:
        return self._app

    def _get_webhook_url(self, agent: str) -> str | None:
        # Search across all instances first
        for instance in get_all_instances(self.config).values():
            agent_config = instance.agents.get(agent)
            if agent_config:
                return agent_config.webhook_url
        # Fallback to legacy top-level agents
        agent_config = self.config.discord.agents.get(agent)
        if agent_config:
            return agent_config.webhook_url
        return None

    @property
    def _agent_names(self) -> list[str]:
        names: set[str] = set(self.config.discord.agents.keys())
        for instance in get_all_instances(self.config).values():
            names.update(instance.agents.keys())
        return sorted(names)

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def _send_webhook(
        self,
        url: str,
        *,
        content: str = "",
        username: str = "FactoryLM",
    ) -> bool:
        """Send a message via Discord webhook. Extracted from AgentRelay pattern."""
        try:
            session = await self._get_session()
            payload: dict[str, Any] = {"username": username}
            if content:
                payload["content"] = content
            async with session.post(url, json=payload) as resp:
                if resp.status in (200, 204):
                    # Update heartbeat on successful message relay
                    self._last_heartbeat = time.time()
                    return True
                logger.warning("Webhook returned %s: %s", resp.status, await resp.text())
                return False
        except Exception:
            logger.exception("Failed to send webhook")
            return False

    async def _handle_relay(self, request: web.Request) -> web.Response:
        """POST /relay — {agent, message, format} → queue → 202."""
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "Invalid JSON"}, status=400)

        agent = body.get("agent", "")
        message = body.get("message", "")

        if not agent or not message:
            return web.json_response(
                {"error": "Both 'agent' and 'message' are required"}, status=400
            )

        webhook_url = self._get_webhook_url(agent)
        if not webhook_url:
            return web.json_response(
                {"error": f"Unknown agent: {agent}", "known_agents": self._agent_names},
                status=404,
            )

        # Route through rate limiter
        payload = {"content": message, "username": agent.capitalize()}
        queued = await self.rate_limiter.post_message(webhook_url, payload)

        if not queued:
            return web.json_response({"error": "Queue full, try again later"}, status=503)

        self._message_count += 1
        return web.json_response(
            {
                "status": "queued",
                "agent": agent,
                "queue_depth": self.rate_limiter.queue_depth(webhook_url),
            },
            status=202,
        )

    async def _handle_status(self, request: web.Request) -> web.Response:
        """GET /status — agent list, queue depth, uptime, per-instance info."""
        uptime = time.monotonic() - self._start_time
        agents_info = {}

        # Legacy top-level agents
        for name, agent_cfg in self.config.discord.agents.items():
            agents_info[name] = {
                "channel_id": agent_cfg.channel_id,
                "machine": agent_cfg.machine,
                "role": agent_cfg.role,
            }

        # Per-instance info
        instances_info = {}
        for inst_name, inst_cfg in get_all_instances(self.config).items():
            inst_agents = {}
            for name, agent_cfg in inst_cfg.agents.items():
                inst_agents[name] = {
                    "channel_id": agent_cfg.channel_id,
                    "machine": agent_cfg.machine,
                    "role": agent_cfg.role,
                }
                # Also add to flat agents list
                if name not in agents_info:
                    agents_info[name] = inst_agents[name]
            instances_info[inst_name] = {
                "guild_id": inst_cfg.guild_id,
                "machine": inst_cfg.machine,
                "role": inst_cfg.role,
                "agents": inst_agents,
            }

        response: dict[str, Any] = {
            "agents": agents_info,
            "queue_depth": self.rate_limiter.total_queue_depth(),
            "messages_relayed": self._message_count,
            "uptime_seconds": round(uptime, 1),
            "shutting_down": self._shutting_down,
        }
        if instances_info:
            response["instances"] = instances_info

        return web.json_response(response)

    async def _handle_health(self, request: web.Request) -> web.Response:
        """GET /health — enhanced health endpoint with uptime, guild count, and heartbeat."""
        uptime = time.monotonic() - self._start_time
        current_time = datetime.datetime.now(datetime.timezone.utc)

        # Format last_heartbeat as ISO string if it exists
        last_heartbeat_iso = None
        if self._last_heartbeat is not None:
            last_heartbeat_iso = datetime.datetime.fromtimestamp(
                self._last_heartbeat, datetime.timezone.utc
            ).isoformat()

        return web.json_response({
            "ok": True,
            "status": "healthy",
            "service": "factorylm-discord-relay",
            "timestamp": current_time.isoformat(),
            "uptime_seconds": round(uptime, 1),
            "guilds_count": max(1, len(get_all_instances(self.config))),
            "guild_id": self.config.discord.guild_id or None,
            "last_heartbeat": last_heartbeat_iso,
            "version": "1.0.0"
        })

    async def _drain_worker(self) -> None:
        """Background task: pull from queue and post to webhooks."""
        while True:
            try:
                item = await self._queue.get()
                agent_name = item["agent"]
                await self._send_webhook(
                    item["webhook_url"],
                    content=item["message"],
                    username=agent_name.capitalize(),
                )
                self._queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Drain worker error")

    async def start(self, host: str | None = None, port: int | None = None) -> None:
        """Start the relay server and drain worker."""
        h = host or self.config.relay.host
        p = port or self.config.relay.port

        self._start_time = time.monotonic()
        self._drain_task = asyncio.create_task(self._drain_worker())

        runner = web.AppRunner(self._app)
        await runner.setup()
        site = web.TCPSite(runner, h, p)
        await site.start()

        logger.info("Relay daemon listening on %s:%d", h, p)

        # Handle shutdown signals
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(self._shutdown(runner)))

        # Keep running
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            pass

    async def _shutdown(self, runner: web.AppRunner) -> None:
        """Graceful shutdown: drain queue, close session, stop server."""
        if self._shutting_down:
            return
        self._shutting_down = True
        logger.info("Shutting down relay daemon...")

        # Drain remaining queue items
        if not self._queue.empty():
            logger.info("Draining %d queued messages...", self._queue.qsize())
            await asyncio.wait_for(self._queue.join(), timeout=10.0)

        if self._drain_task:
            self._drain_task.cancel()

        if self._session and not self._session.closed:
            await self._session.close()

        await runner.cleanup()
        logger.info("Relay daemon stopped.")

        # Stop the event loop
        asyncio.get_running_loop().stop()

    async def close(self) -> None:
        """Close resources (for testing)."""
        if self._drain_task:
            self._drain_task.cancel()
        if self._session and not self._session.closed:
            await self._session.close()
        await self.rate_limiter.close()


def cli_main() -> None:
    """Entry point for factorylm-relay command."""
    import sys

    from factorylm.config import ConfigError, load_config

    try:
        config = load_config()
    except ConfigError as exc:
        print(f"Config error: {exc}")
        sys.exit(1)

    logging.basicConfig(
        level=getattr(logging, config.relay.log_level, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    daemon = AsyncRelayDaemon(config)
    asyncio.run(daemon.start())
