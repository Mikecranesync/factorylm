"""Health check endpoint."""

from fastapi import APIRouter
from sqlalchemy import text

from backend.config import settings
from backend.database import SessionLocal
from backend.models.mes_models import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["meta"])
def health_check():
    """Returns service version and DB connectivity status."""
    db_status = "ok"
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
    except Exception:
        db_status = "unreachable"

    return HealthResponse(
        status="healthy",
        version=settings.api_version,
        db=db_status,
    )
