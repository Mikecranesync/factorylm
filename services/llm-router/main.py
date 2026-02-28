"""FastAPI app — OpenAI-compatible /v1/chat/completions + health endpoints."""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from models import ChatRequest, ChatResponse
from redis_logger import RedisLogger
from router import SmartRouter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger("llm-router")

router = SmartRouter()
redis_logger = RedisLogger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await redis_logger.connect()
    logger.info("LLM Router started — 6 providers loaded")
    yield
    logger.info("LLM Router shutting down")


app = FastAPI(
    title="FactoryLM LLM Router",
    version="1.0.0",
    lifespan=lifespan,
)


@app.post("/v1/chat/completions", response_model=ChatResponse)
async def chat_completions(request: ChatRequest) -> ChatResponse:
    """OpenAI-compatible chat completion endpoint with smart routing."""
    if request.stream:
        raise HTTPException(status_code=501, detail="Streaming not supported (v1)")

    start = time.monotonic()

    try:
        provider_name, response = await router.route(request)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    latency_ms = int((time.monotonic() - start) * 1000)

    logger.info(
        "Routed to %s (model=%s, tokens=%d, latency=%dms)",
        provider_name,
        response.model,
        response.usage.total_tokens,
        latency_ms,
    )

    # Fire-and-forget Redis logging
    await redis_logger.log_request(
        provider=provider_name,
        model=response.model,
        tokens=response.usage.total_tokens,
        latency_ms=latency_ms,
        task_type=request.task_type.value if request.task_type else None,
    )

    return response


@app.get("/health")
async def health() -> JSONResponse:
    """Health check — shows all providers with budget status."""
    return JSONResponse({
        "status": "ok",
        "service": "llm-router",
        "providers": router.get_provider_status(),
    })


@app.get("/health/stats")
async def health_stats() -> JSONResponse:
    """Usage statistics from Redis."""
    stats = await redis_logger.get_stats()
    return JSONResponse({
        "status": "ok",
        "service": "llm-router",
        **stats,
    })
