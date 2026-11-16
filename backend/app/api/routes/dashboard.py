"""Farmer dashboard summary (real counts from the database)."""
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import ConversationHistory, DiseasePrediction, Query, User
from app.schemas.other import FarmerDashboardOut

router = APIRouter(prefix="/dashboard", tags=["Farmer Dashboard"])


@router.get("/summary", response_model=FarmerDashboardOut)
def summary(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    total_queries = db.scalar(select(func.count(Query.id)).where(Query.user_id == user.id)) or 0
    voice_queries = db.scalar(
        select(func.count(Query.id)).where(Query.user_id == user.id, Query.input_mode == "voice")
    ) or 0
    total_conversations = db.scalar(
        select(func.count(ConversationHistory.id)).where(ConversationHistory.user_id == user.id)
    ) or 0
    total_scans = db.scalar(
        select(func.count(DiseasePrediction.id)).where(DiseasePrediction.user_id == user.id)
    ) or 0
    recent_q = db.scalars(
        select(Query).where(Query.user_id == user.id).order_by(Query.created_at.desc()).limit(5)
    ).unique().all()
    recent_p = db.scalars(
        select(DiseasePrediction).where(DiseasePrediction.user_id == user.id)
        .order_by(DiseasePrediction.created_at.desc()).limit(5)
    ).all()
    return {
        "total_queries": total_queries,
        "total_conversations": total_conversations,
        "total_disease_scans": total_scans,
        "voice_queries": voice_queries,
        "recent_questions": [
            {"conversation_id": q.conversation_id, "question": q.original_text,
             "intent": q.intent.name if q.intent else None, "created_at": q.created_at}
            for q in recent_q
        ],
        "recent_predictions": [
            {"id": p.id, "label": p.predicted_label, "disease_name": p.disease.disease_name if p.disease else None,
             "confidence": round(p.confidence, 4), "is_uncertain": p.is_uncertain, "created_at": p.created_at}
            for p in recent_p
        ],
        "has_location": user.latitude is not None and user.longitude is not None,
    }
