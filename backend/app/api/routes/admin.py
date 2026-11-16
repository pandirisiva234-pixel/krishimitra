"""Admin dashboard, statistics, user management and system monitoring."""
import shutil
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query as QueryParam
from sqlalchemy import Date, cast, func, or_, select, text
from sqlalchemy.orm import Session

from app.api.deps import get_services, require_admin
from app.core.config import get_settings
from app.core.exceptions import AppError, NotFoundError
from app.db.session import get_db
from app.models import (
    ROLE_ADMIN,
    ROLE_FARMER,
    Admin,
    Disease,
    DiseasePrediction,
    Document,
    Feedback,
    Intent,
    Language,
    Query,
    Response,
    User,
)
from app.schemas.other import (
    AdminDashboardOut,
    AdminStatisticsOut,
    AdminUserList,
    AdminUserOut,
    AdminUserUpdate,
    SystemStatusOut,
)
from app.services.container import ServiceContainer

router = APIRouter(prefix="/admin", tags=["Admin"])
settings = get_settings()


def _now():
    return datetime.now(timezone.utc)


@router.get("/dashboard", response_model=AdminDashboardOut)
def dashboard(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    count = lambda stmt: db.scalar(stmt) or 0  # noqa: E731
    today = _now().replace(hour=0, minute=0, second=0, microsecond=0)
    helpful = db.execute(
        select(func.count(Feedback.id), func.count(Feedback.id).filter(Feedback.is_helpful.is_(True)))
    ).one()
    return {
        "total_farmers": count(select(func.count(User.id)).where(User.role == ROLE_FARMER)),
        "total_admins": count(select(func.count(User.id)).where(User.role == ROLE_ADMIN)),
        "active_users_7d": count(
            select(func.count(func.distinct(Query.user_id))).where(Query.created_at >= _now() - timedelta(days=7))
        ),
        "new_users_30d": count(select(func.count(User.id)).where(User.role == ROLE_FARMER,
                                                                  User.created_at >= _now() - timedelta(days=30))),
        "total_queries": count(select(func.count(Query.id))),
        "queries_today": count(select(func.count(Query.id)).where(Query.created_at >= today)),
        "total_disease_scans": count(select(func.count(DiseasePrediction.id))),
        "total_documents": count(select(func.count(Document.id)).where(Document.status == "indexed")),
        "helpful_feedback_pct": round(100 * helpful[1] / helpful[0], 1) if helpful[0] else None,
    }


@router.get("/statistics", response_model=AdminStatisticsOut)
def statistics(
    days: int = QueryParam(30, ge=1, le=365),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    since = _now() - timedelta(days=days)

    def pairs(rows):
        return [{"label": str(label), "count": int(n)} for label, n in rows]

    language_usage = db.execute(
        select(Language.name, func.count(Query.id)).join(Query, Query.language_id == Language.id)
        .where(Query.created_at >= since).group_by(Language.name).order_by(func.count(Query.id).desc())
    ).all()
    intents = db.execute(
        select(func.coalesce(Intent.name, "unclassified"), func.count(Query.id))
        .select_from(Query).outerjoin(Intent, Query.intent_id == Intent.id)
        .where(Query.created_at >= since).group_by(Intent.name).order_by(func.count(Query.id).desc())
    ).all()
    diseases = db.execute(
        select(func.coalesce(Disease.disease_name + " (" + Disease.crop + ")", DiseasePrediction.predicted_label),
               func.count(DiseasePrediction.id))
        .select_from(DiseasePrediction).outerjoin(Disease, DiseasePrediction.disease_id == Disease.id)
        .where(DiseasePrediction.created_at >= since)
        .group_by(Disease.disease_name, Disease.crop, DiseasePrediction.predicted_label)
        .order_by(func.count(DiseasePrediction.id).desc()).limit(10)
    ).all()
    day = cast(Query.created_at, Date)
    per_day = db.execute(
        select(day, func.count(Query.id)).where(Query.created_at >= since).group_by(day).order_by(day)
    ).all()
    modes = db.execute(
        select(Query.input_mode, func.count(Query.id)).where(Query.created_at >= since).group_by(Query.input_mode)
    ).all()
    resp = db.execute(
        select(func.avg(Response.total_ms), func.count(Response.id),
               func.count(Response.id).filter(Response.grounded.is_(True)))
        .join(Query, Response.query_id == Query.id).where(Query.created_at >= since)
    ).one()
    return {
        "language_usage": pairs(language_usage),
        "intent_distribution": pairs(intents),
        "disease_distribution": pairs(diseases),
        "queries_per_day": [{"label": d.isoformat(), "count": n} for d, n in per_day],
        "input_modes": pairs(modes),
        "avg_response_ms": round(float(resp[0]), 1) if resp[0] is not None else None,
        "grounded_answer_pct": round(100 * resp[2] / resp[1], 1) if resp[1] else None,
    }


@router.get("/users", response_model=AdminUserList)
def list_users(
    search: str | None = QueryParam(None, max_length=100),
    role: str | None = QueryParam(None, pattern="^(farmer|admin)$"),
    page: int = QueryParam(1, ge=1),
    page_size: int = QueryParam(20, ge=1, le=100),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    q_counts = select(Query.user_id, func.count(Query.id).label("n")).group_by(Query.user_id).subquery()
    stmt = select(User, func.coalesce(q_counts.c.n, 0)).outerjoin(q_counts, q_counts.c.user_id == User.id)
    count_stmt = select(func.count(User.id))
    filters = []
    if search:
        like = f"%{search.strip()}%"
        filters.append(or_(User.full_name.ilike(like), User.phone.ilike(like), User.email.ilike(like),
                           User.district.ilike(like)))
    if role:
        filters.append(User.role == role)
    for f in filters:
        stmt, count_stmt = stmt.where(f), count_stmt.where(f)
    total = db.scalar(count_stmt) or 0
    rows = db.execute(stmt.order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return {
        "items": [_admin_user(u, n) for u, n in rows],
        "total": total, "page": page, "page_size": page_size,
    }


def _admin_user(u: User, n: int) -> dict:
    return {
        "id": u.id, "full_name": u.full_name, "phone": u.phone, "email": u.email, "role": u.role,
        "language_code": u.preferred_language.code, "district": u.district, "state": u.state,
        "is_active": u.is_active, "query_count": n, "created_at": u.created_at, "last_login_at": u.last_login_at,
    }


@router.patch("/users/{user_id}", response_model=AdminUserOut)
def update_user(user_id: int, body: AdminUserUpdate, admin: User = Depends(require_admin),
                db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if user is None:
        raise NotFoundError("User not found")
    if user.id == admin.id and (body.is_active is False or body.role == ROLE_FARMER):
        raise AppError("You cannot disable or demote your own account", code="self_change", status_code=400)
    if body.is_active is not None:
        user.is_active = body.is_active
    if body.role is not None and body.role != user.role:
        user.role = body.role
        if body.role == ROLE_ADMIN and user.admin_profile is None:
            db.add(Admin(user_id=user.id, designation="Administrator"))
    db.commit()
    db.refresh(user)
    n = db.scalar(select(func.count(Query.id)).where(Query.user_id == user.id)) or 0
    return _admin_user(user, n)


@router.get("/system", response_model=SystemStatusOut)
def system_status(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
    services: ServiceContainer = Depends(get_services),
):
    try:
        db.execute(text("SELECT 1"))
        database = "ok"
    except Exception:  # noqa: BLE001
        database = "unreachable"
    try:
        chunks = services.vector_store.count()
        vector = "ok"
    except Exception:  # noqa: BLE001
        chunks, vector = None, "unavailable"
    storage_bytes = sum(p.stat().st_size for p in settings.STORAGE_DIR.rglob("*") if p.is_file()) \
        if settings.STORAGE_DIR.exists() else 0
    return {
        "database": database,
        "vector_store": vector,
        "vector_chunks": chunks,
        "gemini_configured": services.llm.is_configured,
        "gemini_model": services.llm.model,
        "openweather_configured": services.weather.client.is_configured,
        "disease_model_available": services.disease.is_available,
        "intent_model_available": services.intent.is_available,
        "models_loaded": services.models_loaded(),
        "disk_free_gb": round(shutil.disk_usage(settings.STORAGE_DIR).free / 1e9, 1),
        "storage_used_mb": round(storage_bytes / 1e6, 1),
    }
