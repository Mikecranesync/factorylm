"""FactoryLM MES API — FastAPI entry point.

Lifespan:
  startup  → launch state poller + OEE calculator background tasks
  shutdown → stop both tasks cleanly

Routes (cumulative by week):
  Week 1: /api/health
  Week 2: /api/mes/lines,  /api/mes/lines/{id}/state
  Week 3: /api/mes/lines/{id}/oee,  /api/mes/lines/{id}/oee/history
          /api/mes/oee/summary,     /api/mes/kpis
  Week 4: /api/mes/products,        /api/mes/products (POST/GET)
          /api/mes/work-orders (POST/GET),  /api/mes/work-orders/{id} (GET)
          /api/mes/work-orders/{id}/status (PATCH)
          Schedule-aware TEEP via schedules table
  Week 5: /api/mes/downtime-reasons
          /api/mes/lines/{id}/downtime (GET/POST)
          NLP classifier: free-text → reason_code
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.routes.downtime import router as downtime_router
from backend.routes.health import router as health_router
from backend.routes.lines import router as lines_router
from backend.routes.oee import router as oee_router
from backend.routes.work_orders import router as work_orders_router
from backend.services import oee_calculator, state_poller

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db_host = settings.database_url.split("@")[-1]
    logger.info("MES service starting — DB: %s  PLC: %s", db_host, settings.plc_modbus_url)

    poller_task = oee_task = None

    if not settings.plc_use_mock:
        poller_task = asyncio.create_task(
            state_poller.run(poll_interval_sec=settings.plc_poll_interval_sec),
            name="state_poller",
        )
        oee_task = asyncio.create_task(
            oee_calculator.run(tick_sec=settings.oee_tick_sec),
            name="oee_calculator",
        )
        logger.info(
            "Background tasks started — poller=%ds  oee_tick=%ds",
            settings.plc_poll_interval_sec, settings.oee_tick_sec,
        )
    else:
        logger.info("PLC mock mode — background tasks disabled")

    yield

    logger.info("MES service shutting down")
    state_poller.stop()
    oee_calculator.stop()
    for task in [t for t in [poller_task, oee_task] if t]:
        try:
            await asyncio.wait_for(task, timeout=8.0)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            task.cancel()


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

app.include_router(health_router,       prefix=settings.api_prefix)
app.include_router(lines_router,        prefix=settings.api_prefix)
app.include_router(oee_router,          prefix=settings.api_prefix)
app.include_router(work_orders_router,  prefix=settings.api_prefix)
app.include_router(downtime_router,     prefix=settings.api_prefix)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8300, reload=True)
