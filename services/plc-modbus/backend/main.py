"""FastAPI application entry point."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.routes import setup_router, plc_router, ws_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ---------- OpenTelemetry (no-op if packages missing) ----------
try:
    from factorylm.observability import init_tracing, tracing_health, create_span

    init_tracing("plc-modbus")
except ImportError:
    # factorylm core not installed — tracing simply disabled
    def tracing_health():  # type: ignore[misc]
        return {"enabled": False, "service_name": "plc-modbus", "endpoint": ""}

    from contextlib import contextmanager as _cm

    @_cm
    def create_span(name, attributes=None):  # type: ignore[misc]
        yield None

# Create FastAPI app
app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    docs_url=f"{settings.api_prefix}/docs",
    redoc_url=f"{settings.api_prefix}/redoc",
    openapi_url=f"{settings.api_prefix}/openapi.json",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get(f"{settings.api_prefix}/health")
async def health_check() -> dict:
    """Health check endpoint."""
    with create_span("health-check"):
        return {
            "status": "healthy",
            "version": settings.api_version,
        }


@app.get(f"{settings.api_prefix}/tracing-health")
async def tracing_health_check() -> dict:
    """Diagnostic endpoint for tracing status."""
    return tracing_health()


# Include routers
app.include_router(setup_router, prefix=settings.api_prefix)
app.include_router(plc_router, prefix=settings.api_prefix)
app.include_router(ws_router)  # WebSocket at root level (not under /api)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
    )
