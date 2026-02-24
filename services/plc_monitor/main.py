"""PLC Monitor service entrypoint.

Run: python -m services.plc_monitor.main
"""

import asyncio
import logging
import signal
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure repo root is on sys.path for cosmos.* imports
_repo_root = str(Path(__file__).resolve().parent.parent.parent)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

from aiohttp import web

from services.plc_monitor.config import MonitorConfig
from services.plc_monitor.monitor import PLCMonitor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("plc-monitor")

_start_time = datetime.now(tz=timezone.utc)
_monitor: PLCMonitor | None = None


async def health_check(request: web.Request) -> web.Response:
    """HTTP health check endpoint."""
    uptime = int((datetime.now(tz=timezone.utc) - _start_time).total_seconds())
    stats = _monitor.get_stats() if _monitor else {}

    # Quick Matrix API reachability check
    matrix_ok = False
    if _monitor:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=3.0) as client:
                r = await client.get(f"{_monitor.config.matrix_url}/api/health")
                matrix_ok = r.status_code == 200
        except Exception:
            pass

    return web.json_response({
        "status": "ok",
        "service": "plc-monitor",
        "uptime_seconds": uptime,
        "matrix_reachable": matrix_ok,
        **stats,
    })


async def run_health_server(port: int) -> web.AppRunner:
    """Start the aiohttp health server."""
    app = web.Application()
    app.router.add_get("/health", health_check)
    app.router.add_get("/", health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info("Health server listening on port %d", port)
    return runner


async def main() -> None:
    global _monitor

    config = MonitorConfig.from_env()
    _monitor = PLCMonitor(config)

    # Start health server
    runner = await run_health_server(config.health_port)

    # Graceful shutdown
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _shutdown(sig: signal.Signals) -> None:
        logger.info("Received %s, shutting down...", sig.name)
        stop_event.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _shutdown, sig)

    # Run monitor until stop signal
    monitor_task = asyncio.create_task(_monitor.start())

    await stop_event.wait()

    # Cleanup
    await _monitor.stop()
    monitor_task.cancel()
    try:
        await monitor_task
    except asyncio.CancelledError:
        pass
    await runner.cleanup()
    logger.info("PLC Monitor shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
