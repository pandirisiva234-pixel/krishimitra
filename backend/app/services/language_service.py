"""Database helpers for languages (the `languages` table is the source of truth)."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models import Language


def active_languages(db: Session) -> list[Language]:
    return list(db.scalars(select(Language).where(Language.is_active.is_(True)).order_by(Language.id)))


def get_language(db: Session, code: str) -> Language:
    lang = db.scalars(select(Language).where(Language.code == code, Language.is_active.is_(True))).first()
    if not lang:
        raise AppError(f"Language '{code}' is not supported", code="unsupported_language", status_code=422)
    return lang


def get_language_by_whisper_code(db: Session, whisper_code: str) -> Language | None:
    return db.scalars(
        select(Language).where(Language.whisper_code == whisper_code, Language.is_active.is_(True))
    ).first()


def script_map(db: Session) -> dict[str, str]:
    # Hindi and Marathi share Devanagari: the first language listed (Hindi) is the default for the script;
    # the farmer's selected language decides between them (see AssistantService.ask)
    out: dict[str, str] = {}
    for lang in active_languages(db):
        out.setdefault(lang.script, lang.code)
    return out
