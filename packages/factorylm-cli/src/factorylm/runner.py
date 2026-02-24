"""Async orchestrator — starts all subsystems as concurrent tasks.

Used by `factorylm up` to run collector, API, Discord, and monitor together.
"""

from __future__ import annotations

import asyncio
import logging
import signal
from datetime import datetime, timezone
from typing import Any

from factorylm.config import FactoryLMConfig
from factorylm.db.store import TagStore
from factorylm.plc.factory import create_client_from_config

logger = logging.getLogger(__name__)


async def collect_loop(cfg: FactoryLMConfig, store: TagStore) -> None:
    """PLC -> SQLite collector loop."""
    client = create_client_from_config(cfg.plc)
    if not client.connect():
        logger.error("Cannot connect to PLC at %s:%d — collector stopped", cfg.plc.host, cfg.plc.port)
        return

    logger.info("Collector started — %s @ %s:%d (every %.1fs)",
                 cfg.plc.type, cfg.plc.host, cfg.plc.port, cfg.plc.poll_interval)
    try:
        while True:
            try:
                tags = client.read_tags()
                store.insert_tags(tags)
                logger.debug("Collected %d tags", len(tags))
            except ConnectionError:
                logger.warning("PLC connection lost, reconnecting...")
                client.connect()
            except Exception:
                logger.exception("Collector read error")
            await asyncio.sleep(cfg.plc.poll_interval)
    finally:
        client.disconnect()


async def run_api(cfg: FactoryLMConfig, store: TagStore) -> None:
    """Start FastAPI web dashboard."""
    try:
        from factorylm.api.server import run_server_async
        logger.info("API server starting on %s:%d", cfg.api.host, cfg.api.port)
        await run_server_async(store, host=cfg.api.host, port=cfg.api.port)
    except ImportError:
        logger.warning("FastAPI not installed — skipping API server. pip install 'factorylm[api]'")


async def run_discord_bot(cfg: FactoryLMConfig, store: TagStore) -> None:
    """Start Discord bot."""
    if not cfg.discord.token:
        logger.info("No Discord token configured — skipping bot")
        return
    try:
        from factorylm.discord.bot import FactoryLMBot
        bot = FactoryLMBot(
            token=cfg.discord.token,
            store=store,
            bot_name=cfg.discord.bot_name,
            mention_only=cfg.discord.mention_only,
        )
        logger.info("Discord bot starting as '%s'", cfg.discord.bot_name)
        await bot.start()
    except ImportError:
        logger.warning("discord.py not installed — skipping bot. pip install 'factorylm[discord]'")


async def run_monitor(cfg: FactoryLMConfig, store: TagStore) -> None:
    """Start fault watcher."""
    if not cfg.monitor.enabled:
        return
    from factorylm.monitor.watcher import FaultWatcher
    from factorylm.cosmos.client import CosmosClient

    cosmos = CosmosClient(api_key=cfg.cosmos.api_key, model=cfg.cosmos.model)
    watcher = FaultWatcher(store=store, cosmos=cosmos, poll_interval=cfg.monitor.poll_interval)
    await watcher.run()


async def run_all(cfg: FactoryLMConfig) -> None:
    """Start all subsystems concurrently."""
    store = TagStore(db_path=cfg.db.path)
    logger.info("FactoryLM starting — all subsystems")

    # Graceful shutdown on SIGINT/SIGTERM
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _signal_handler():
        logger.info("Shutdown signal received")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _signal_handler)
        except NotImplementedError:
            pass  # Windows

    tasks = [
        asyncio.create_task(collect_loop(cfg, store), name="collector"),
        asyncio.create_task(run_api(cfg, store), name="api"),
        asyncio.create_task(run_discord_bot(cfg, store), name="discord"),
        asyncio.create_task(run_monitor(cfg, store), name="monitor"),
    ]

    # Wait for stop signal or any task to fail
    done, pending = await asyncio.wait(
        [*tasks, asyncio.create_task(stop_event.wait())],
        return_when=asyncio.FIRST_COMPLETED,
    )

    logger.info("Shutting down subsystems...")
    for t in pending:
        t.cancel()
    await asyncio.gather(*pending, return_exceptions=True)
    logger.info("FactoryLM stopped")
