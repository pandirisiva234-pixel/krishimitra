"""Farmer dashboard summary (real counts from the database)."""
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import Date, cast, func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import ConversationHistory, Disease, DiseasePrediction, Intent, Query, User
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
        **_charts(db, user.id),
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


def fill_days(rows, days: int, today: date | None = None) -> list[dict]:
    """[(date, n), ...] -> one entry per day for the last `days` days, with 0 for days without data."""
    today = today or datetime.now(timezone.utc).date()
    counts = {d if isinstance(d, date) else date.fromisoformat(str(d)): int(n) for d, n in rows}
    return [{"label": (today - timedelta(days=i)).isoformat(), "count": counts.get(today - timedelta(days=i), 0)}
            for i in range(days - 1, -1, -1)]


def scan_outcome_counts(db: Session, *where) -> list[dict]:
    """Leaf scans split into healthy, disease found and unsure (empty groups left out)."""
    rows = db.execute(
        select(DiseasePrediction.is_uncertain, Disease.is_healthy, func.count(DiseasePrediction.id))
        .select_from(DiseasePrediction).outerjoin(Disease, DiseasePrediction.disease_id == Disease.id)
        .where(*where).group_by(DiseasePrediction.is_uncertain, Disease.is_healthy)
    ).all()
    out = {"healthy": 0, "disease": 0, "uncertain": 0}
    for uncertain, healthy, n in rows:
        out["uncertain" if uncertain else "healthy" if healthy else "disease"] += int(n)
    return [{"label": k, "count": v} for k, v in out.items() if v]


def _charts(db: Session, user_id: int) -> dict:
    since = datetime.now(timezone.utc) - timedelta(days=14)
    day = cast(Query.created_at, Date)
    per_day = db.execute(
        select(day, func.count(Query.id)).where(Query.user_id == user_id, Query.created_at >= since).group_by(day)
    ).all()
    topics = db.execute(
        select(func.coalesce(Intent.name, "other"), func.count(Query.id))
        .select_from(Query).outerjoin(Intent, Query.intent_id == Intent.id)
        .where(Query.user_id == user_id).group_by(Intent.name).order_by(func.count(Query.id).desc())
    ).all()
    return {
        "activity_14d": fill_days(per_day, 14),
        "topics": [{"label": str(k), "count": int(n)} for k, n in topics],
        "scan_outcomes": scan_outcome_counts(db, DiseasePrediction.user_id == user_id),
    }
