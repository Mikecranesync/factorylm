"""FactoryLM MES API — FastAPI entry point.

Week 1: /health only.
Week 2+: lines, work_orders, downtime, oee routes added here.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.routes.health import router as health_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("MES service starting — DB: %s", settings.database_url.split("@")[-1])
    yield
    logger.info("MES service stopping")


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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8300, reload=True)
