"""
Health Check Router
===================
"""

from datetime import datetime
from fastapi import APIRouter
from backend.config import settings

router = APIRouter()


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/ready")
async def readiness_check():
    """Readiness check - verifies dependencies"""
    checks = {
        "database": True,  # TODO: actual DB check
        "telegram": bool(settings.TELEGRAM_BOT_TOKEN),
        "anthropic": bool(settings.ANTHROPIC_API_KEY),
    }
    
    all_ready = all(checks.values())
    
    return {
        "ready": all_ready,
        "checks": checks,
        "timestamp": datetime.utcnow().isoformat()
    }
