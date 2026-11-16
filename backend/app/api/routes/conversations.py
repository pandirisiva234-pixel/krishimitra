"""Conversation history for the logged-in farmer."""
from fastapi import APIRouter, Depends, Query as QueryParam
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.exceptions import NotFoundError
from app.db.session import get_db
from app.models import ConversationHistory, Query, User
from app.schemas.assistant import ConversationDetail, ConversationSummary
from app.schemas.auth import MessageResponse
from app.services.assistant import audio_url

router = APIRouter(prefix="/conversations", tags=["Conversations"])


def _message(q: Query) -> dict:
    r = q.response
    return {
        "query_id": q.id,
        "response_id": r.id if r else None,
        "question": q.original_text,
        "question_english": q.english_text,
        "answer": r.answer_text if r else None,
        "answer_english": r.answer_english if r else None,
        "intent": q.intent.name if q.intent else None,
        "input_mode": q.input_mode,
        "grounded": r.grounded if r else None,
        "sources": r.sources if r else [],
        "has_audio": bool(r and r.audio_path),
        "audio_url": audio_url(r.audio_path) if r else None,
        "created_at": q.created_at,
    }


@router.get("", response_model=list[ConversationSummary])
def list_conversations(
    limit: int = QueryParam(50, ge=1, le=200),
    offset: int = QueryParam(0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    counts = (
        select(Query.conversation_id, func.count(Query.id).label("n"))
        .group_by(Query.conversation_id).subquery()
    )
    rows = db.execute(
        select(ConversationHistory, func.coalesce(counts.c.n, 0))
        .outerjoin(counts, counts.c.conversation_id == ConversationHistory.id)
        .where(ConversationHistory.user_id == user.id)
        .order_by(ConversationHistory.updated_at.desc())
        .limit(limit).offset(offset)
    ).all()
    return [
        {"id": c.id, "title": c.title, "language_code": c.language.code, "message_count": n,
         "created_at": c.created_at, "updated_at": c.updated_at}
        for c, n in rows
    ]


@router.get("/{conversation_id}", response_model=ConversationDetail)
def get_conversation(conversation_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    conv = db.get(ConversationHistory, conversation_id)
    if conv is None or conv.user_id != user.id:
        raise NotFoundError("Conversation not found")
    messages = [_message(q) for q in conv.queries]
    return {"id": conv.id, "title": conv.title, "language_code": conv.language.code,
            "message_count": len(messages), "created_at": conv.created_at, "updated_at": conv.updated_at,
            "messages": messages}


@router.delete("/{conversation_id}", response_model=MessageResponse)
def delete_conversation(conversation_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    conv = db.get(ConversationHistory, conversation_id)
    if conv is None or conv.user_id != user.id:
        raise NotFoundError("Conversation not found")
    db.delete(conv)
    db.commit()
    return MessageResponse(message="Conversation deleted")
