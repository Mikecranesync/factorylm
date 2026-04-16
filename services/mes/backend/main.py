"""FactoryLM MES API — FastAPI entry point.

Lifespan:
  startup  → seed state cache, launch background state poller
  shutdown → signal poller to stop cleanly

Routes (cumulative by week):
  Week 1: /api/health
  Week 2: /api/mes/lines,  /api/mes/lines/{id}/state
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.routes.health import router as health_router
from backend.routes.lines import router as lines_router
from backend.services import state_poller

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db_host = settings.database_url.split("@")[-1]
    logger.info("MES service starting — DB: %s  PLC: %s", db_host, settings.plc_modbus_url)

    poller_task = None
    if not settings.plc_use_mock:
        poller_task = asyncio.create_task(
            state_poller.run(poll_interval_sec=settings.plc_poll_interval_sec),
            name="state_poller",
        )
        logger.info("State poller started (interval=%ds)", settings.plc_poll_interval_sec)
    else:
        logger.info("PLC mock mode — state poller disabled")

    yield

    logger.info("MES service shutting down")
    if poller_task:
        state_poller.stop()
        try:
            await asyncio.wait_for(poller_task, timeout=8.0)
        except asyncio.TimeoutError:
            poller_task.cancel()


app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    docs_url=f"{settings.api_prefix}/docs",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix=settings.api_prefix)
app.include_router(lines_router, prefix=settings.api_prefix)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8300, reload=True)
