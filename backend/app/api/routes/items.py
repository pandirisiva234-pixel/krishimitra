"""Farm item identification from a photo (pesticide bottle, fertilizer bag, seed packet, tool...)."""
from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_services
from app.api.routes.assistant import get_assistant
from app.core.config import get_settings
from app.core.exceptions import ServiceNotConfiguredError
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.models import User
from app.services.assistant import AssistantService
from app.services.container import ServiceContainer
from app.services.language_service import get_language
from app.services.vision.item_identifier import identify_item, summary_text
from app.utils.files import read_validated_upload

router = APIRouter(prefix="/items", tags=["Farm item identification"])
settings = get_settings()
MIME = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}


@router.post("/identify")
@limiter.limit(settings.RATE_LIMIT_AI)
async def identify(
    request: Request,
    image: UploadFile = File(...),
    language_code: str | None = Form(None, max_length=8),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    services: ServiceContainer = Depends(get_services),
    assistant: AssistantService = Depends(get_assistant),
):
    """Photo of a farm item -> what it is, what it is for, how to use it safely (English + farmer's language)."""
    if not services.llm.is_configured:
        raise ServiceNotConfiguredError("Item identification needs GEMINI_API_KEY in backend/.env")
    data, ext = await read_validated_upload(image, kind="image", max_mb=settings.MAX_IMAGE_MB)
    item = await identify_item(services.llm, data, MIME.get(ext, "image/jpeg"))
    lang = get_language(db, language_code) if language_code else user.preferred_language
    text_en = summary_text(item)
    text_local = text_en if lang.code == "en" else await assistant.translate(text_en, "eng_Latn", lang.nllb_code)
    return {**item, "summary_english": text_en, "summary": text_local, "language_code": lang.code}
