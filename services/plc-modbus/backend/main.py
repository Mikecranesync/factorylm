"""FastAPI application entry point."""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.config import settings
from backend.routes import setup_router, plc_router, ws_router, discovery_router
from backend.services.discovery_daemon import discovery_daemon

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start/stop discovery daemon with the app."""
    if settings.mock_mode:
        logger.info("Mock mode enabled — using simulated PLC, discovery disabled")
        # Auto-connect the mock PLC so /api/plc/io works immediately
        from backend.services.plc_connection import plc_service
        plc_service.connect("mock", 0)
    elif settings.discovery_enabled:
        await discovery_daemon.start()
        logger.info("Discovery daemon started")
    yield
    if not settings.mock_mode and settings.discovery_enabled:
        await discovery_daemon.stop()
        logger.info("Discovery daemon stopped")


# Create FastAPI app
app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    docs_url=f"{settings.api_prefix}/docs",
    redoc_url=f"{settings.api_prefix}/redoc",
    openapi_url=f"{settings.api_prefix}/openapi.json",
    lifespan=lifespan,
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
app.include_router(discovery_router, prefix=settings.api_prefix)
app.include_router(ws_router)  # WebSocket at root level (not under /api)

# Serve static files and dashboard
_static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(_static_dir):
    app.mount("/static", StaticFiles(directory=_static_dir), name="static")


@app.get("/")
async def dashboard():
    """Serve the live discovery dashboard."""
    index = os.path.join(_static_dir, "index.html")
    if os.path.isfile(index):
        return FileResponse(index)
    return {"message": "Pi Factory API", "docs": f"{settings.api_prefix}/docs"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=settings.discovery_port,
        reload=True,
    )
