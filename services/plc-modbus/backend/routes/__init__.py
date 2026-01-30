"""API route modules."""

from .setup import router as setup_router
from .plc import router as plc_router
from .websocket import router as ws_router

__all__ = ["setup_router", "plc_router", "ws_router"]
