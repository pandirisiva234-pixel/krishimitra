"""Health check and public metadata (languages)."""
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.schemas.auth import LanguageOut
from app.services.language_service import active_languages

router = APIRouter(tags=["Meta"])


@router.get("/health")
def health(db: Session = Depends(get_db)):
    """Liveness + database check. Used by Docker and the admin system page."""
    try:
        db.execute(text("SELECT 1"))
        database = "ok"
    except Exception:  # noqa: BLE001
        database = "unreachable"
    settings = get_settings()
    return {"status": "ok" if database == "ok" else "degraded", "database": database,
            "environment": settings.ENVIRONMENT, "version": "1.0.0"}


@router.get("/languages", response_model=list[LanguageOut])
def list_languages(db: Session = Depends(get_db)):
    return active_languages(db)
