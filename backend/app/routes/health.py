import logging

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.database.connection import get_db
from app.services.ai_provider import get_ai_provider

router = APIRouter()
logger = logging.getLogger("routes.health")


@router.get("/health")
def health_check(db: Session = Depends(get_db)):
    """Liveness plus the dependencies a request actually needs.

    Makes no provider request and spends nothing. Reports whether keys are
    configured, never their values. ``status`` is "degraded" when the database
    cannot be queried, because every module reads or writes it.
    """
    try:
        db.execute(text("SELECT 1"))
        database = "ok"
    except Exception:
        logger.exception("health check: database query failed")
        database = "error"

    return {
        "status": "ok" if database == "ok" else "degraded",
        "service": "market-radar-api",
        "database": database,
        "serpapi_configured": bool(settings.SERPAPI_API_KEY),
        "ai_provider_configured": get_ai_provider().is_configured(),
    }
