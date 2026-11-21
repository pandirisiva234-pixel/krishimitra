"""Voice transcription, assistant questions, text-to-speech and feedback."""
from fastapi import APIRouter, Depends, File, Form, Query as QueryParam, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_services
from app.core.config import get_settings
from app.core.exceptions import ConflictError, NotFoundError
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.models import Feedback, Query, Response, User
from app.schemas.assistant import AskRequest, AskResponse, FeedbackRequest, SpeakRequest, TranscriptionOut, TranslateRequest
from app.schemas.auth import MessageResponse
from app.services.assistant import AssistantService, audio_url
from app.services.container import ServiceContainer
from app.services.language_service import get_language
from app.services.videos.youtube_client import plan_search
from app.utils.files import read_validated_upload, safe_child

settings = get_settings()
voice_router = APIRouter(prefix="/voice", tags=["Voice"])
router = APIRouter(prefix="/assistant", tags=["Assistant"])
feedback_router = APIRouter(prefix="/feedback", tags=["Feedback"])


def get_assistant(services: ServiceContainer = Depends(get_services)) -> AssistantService:
    return AssistantService(services, settings)


@voice_router.post("/transcribe", response_model=TranscriptionOut)
@limiter.limit(settings.RATE_LIMIT_AI)
async def transcribe(
    request: Request,
    audio: UploadFile = File(..., description="Recording (webm, wav, mp3, ogg, m4a), max 60 s"),
    language_hint: str | None = Form(None, max_length=8, description="Language selected on screen"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    assistant: AssistantService = Depends(get_assistant),
):
    data, ext = await read_validated_upload(audio, kind="audio", max_mb=settings.MAX_AUDIO_MB)
    return await assistant.transcribe(db, user, data, ext, language_hint)


@router.post("/query", response_model=AskResponse)
@limiter.limit(settings.RATE_LIMIT_AI)
async def ask(
    request: Request,
    body: AskRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    assistant: AssistantService = Depends(get_assistant),
):
    """Answer a farming question (typed, or a transcript from /voice/transcribe)."""
    return await assistant.ask(db, user, body)


@router.post("/speak")
@limiter.limit(settings.RATE_LIMIT_TTS)
async def speak(
    request: Request,
    body: SpeakRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    services: ServiceContainer = Depends(get_services),
    assistant: AssistantService = Depends(get_assistant),
):
    """Convert text to speech in a language. Set translate_from_english to translate English text first
    (used to read disease advice aloud). Returns {"audio_url", "text"}."""
    lang = get_language(db, body.language_code)
    text = body.text
    if body.translate_from_english and lang.code != "en":
        text = await assistant.translate(text, "eng_Latn", lang.nllb_code)
    path = await services.tts.synthesize(text, lang.tts_voice, gtts_lang=lang.code)
    return {"audio_url": audio_url(str(path)), "text": text, "language_code": lang.code}


@router.post("/translate")
@limiter.limit(settings.RATE_LIMIT_TTS)
async def translate_text(
    request: Request,
    body: TranslateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    assistant: AssistantService = Depends(get_assistant),
):
    """Translate English text (e.g. disease advice) into a language; line breaks are kept."""
    lang = get_language(db, body.language_code)
    if lang.code == "en":
        return {"text": body.text, "language_code": "en"}
    text = await assistant.translate(body.text, "eng_Latn", lang.nllb_code)
    return {"text": text, "language_code": lang.code}


@router.get("/videos")
@limiter.limit(settings.RATE_LIMIT_TTS)
async def related_videos(
    request: Request,
    q: str = QueryParam(..., min_length=2, max_length=500, description="The question in English"),
    language_code: str = QueryParam("en", max_length=8),
    original: str | None = QueryParam(None, max_length=500, description="The question as the farmer asked it"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    services: ServiceContainer = Depends(get_services),
):
    """Up to 3 related YouTube videos for a farming question, searched in the farmer's language.
    Only videos that name the crop are kept; trusted farming channels (DD Kisan, ICAR, KVKs) come first.
    Returns {"enabled": false} when no YouTube key is set, so the app just hides the section."""
    if not services.videos.is_configured:
        return {"enabled": False, "query": None, "videos": []}
    lang = get_language(db, language_code)
    plan = await plan_search(services.llm, q, original, lang.name, timeout=settings.LLM_REFINE_TIMEOUT_S)
    result = await services.videos.related_videos(q, lang.code, plan)
    return {"enabled": True, **result}


@router.get("/audio/{filename}")
def get_audio(filename: str, user: User = Depends(get_current_user)):
    path = safe_child(settings.tts_dir, filename)
    return FileResponse(path, media_type="audio/mpeg")


@feedback_router.post("", response_model=MessageResponse, status_code=201)
def give_feedback(body: FeedbackRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    response = db.get(Response, body.response_id)
    if response is None:
        raise NotFoundError("Answer not found")
    owner = db.scalars(select(Query.user_id).where(Query.id == response.query_id)).first()
    if owner != user.id:
        raise NotFoundError("Answer not found")
    existing = db.scalars(
        select(Feedback).where(Feedback.response_id == body.response_id, Feedback.user_id == user.id)
    ).first()
    if existing:
        raise ConflictError("Feedback already given for this answer")
    db.add(Feedback(response_id=body.response_id, user_id=user.id, is_helpful=body.is_helpful,
                    comment=body.comment))
    db.commit()
    return MessageResponse(message="Thank you for your feedback")
