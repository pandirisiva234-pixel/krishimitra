"""Plant disease prediction and history."""
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Query as QueryParam, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.api.deps import get_current_user, get_services
from app.core.config import get_settings
from app.core.exceptions import FileValidationError, NotFoundError, ServiceNotConfiguredError
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.models import Disease, DiseasePrediction, User
from app.schemas.other import DiseaseInfoOut, DiseasePredictionOut
from app.services.container import ServiceContainer
from app.services.disease.predictor import BLUR_THRESHOLD
from app.services.language_service import get_language
from app.services.vision.second_opinion import NOTE, second_opinion, summary_text
from app.utils.files import read_validated_upload, safe_child, save_bytes

router = APIRouter(prefix="/disease", tags=["Plant Disease"])
settings = get_settings()


def _serialize(pred: DiseasePrediction, diseases_by_label: dict[str, Disease]) -> dict:
    top = []
    for item in pred.top_predictions or []:
        d = diseases_by_label.get(item["label"])
        top.append({"label": item["label"], "confidence": item["confidence"],
                    "crop": d.crop if d else None, "disease_name": d.disease_name if d else None})
    is_blurry = pred.blur_score is not None and pred.blur_score < BLUR_THRESHOLD
    if pred.is_uncertain:
        message = ("The model is not confident about this photo. Retake a clear, close photo of one affected "
                   "leaf in daylight, or consult an agriculture officer.")
    elif pred.disease and pred.disease.is_healthy:
        message = "The leaf looks healthy."
    else:
        message = "Possible disease detected. Check the symptoms below to confirm before treating."
    if is_blurry:
        message += " The photo looks blurry, which lowers accuracy."
    return {
        "id": pred.id,
        "predicted_label": pred.predicted_label,
        "confidence": round(pred.confidence, 4),
        "is_uncertain": pred.is_uncertain,
        "message": message,
        "top_predictions": top,
        "disease": DiseaseInfoOut.model_validate(pred.disease) if pred.disease else None,
        "blur_score": round(pred.blur_score, 1) if pred.blur_score is not None else None,
        "is_blurry": is_blurry,
        "model_version": pred.model_version,
        "inference_ms": pred.inference_ms,
        "image_url": f"/api/disease/images/{Path(pred.image_path).name}",
        "created_at": pred.created_at,
    }


def _diseases_for(db: Session, preds: list[DiseasePrediction]) -> dict[str, Disease]:
    labels = {item["label"] for p in preds for item in (p.top_predictions or [])}
    if not labels:
        return {}
    return {d.class_label: d for d in db.scalars(select(Disease).where(Disease.class_label.in_(labels)))}


@router.post("/predict", response_model=DiseasePredictionOut, status_code=201)
@limiter.limit(settings.RATE_LIMIT_AI)
async def predict(
    request: Request,
    image: UploadFile = File(..., description="Leaf photo (jpg, png, webp), max 5 MB"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    services: ServiceContainer = Depends(get_services),
):
    data, ext = await read_validated_upload(image, kind="image", max_mb=settings.MAX_IMAGE_MB)
    try:
        result = await run_in_threadpool(services.disease.predict, data)
    except ValueError as exc:
        raise FileValidationError("Could not read this image. Try a JPG or PNG photo.") from exc
    path = save_bytes(data, settings.image_dir, ext)
    disease = db.scalars(select(Disease).where(Disease.class_label == result.label)).first()
    pred = DiseasePrediction(
        user_id=user.id,
        disease_id=disease.id if disease else None,
        predicted_label=result.label,
        confidence=result.confidence,
        is_uncertain=result.confidence < settings.DISEASE_CONFIDENCE_THRESHOLD,
        top_predictions=[{"label": label, "confidence": round(conf, 4)} for label, conf in result.top],
        blur_score=result.blur,
        image_path=str(path),
        model_version=result.model_version,
        inference_ms=result.inference_ms,
    )
    db.add(pred)
    db.commit()
    db.refresh(pred)
    return _serialize(pred, _diseases_for(db, [pred]))


@router.post("/predictions/{prediction_id}/second-opinion")
@limiter.limit(settings.RATE_LIMIT_AI)
async def ai_second_opinion(
    request: Request,
    prediction_id: int,
    language_code: str | None = Form(None, max_length=8),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    services: ServiceContainer = Depends(get_services),
):
    """Gemini looks at the same photo when the trained model is unsure (clearly labelled as general advice)."""
    from app.api.routes.assistant import get_assistant  # local import avoids a circular import

    pred = db.get(DiseasePrediction, prediction_id)
    if pred is None or pred.user_id != user.id:
        raise NotFoundError("Prediction not found")
    if not services.llm.is_configured:
        raise ServiceNotConfiguredError("The AI second opinion needs GEMINI_API_KEY in backend/.env")
    path = Path(pred.image_path)
    if not path.exists():
        raise NotFoundError("The photo for this prediction is no longer stored")
    mime = {".png": "image/png", ".webp": "image/webp"}.get(path.suffix.lower(), "image/jpeg")
    op = await second_opinion(services.llm, path.read_bytes(), mime)
    lang = get_language(db, language_code) if language_code else user.preferred_language
    text_en = summary_text(op)
    text_local = text_en if lang.code == "en" else await get_assistant(services).translate(
        text_en, "eng_Latn", lang.nllb_code)
    return {**op, "note": NOTE, "summary_english": text_en, "summary": text_local, "language_code": lang.code}


@router.get("/history", response_model=list[DiseasePredictionOut])
def history(
    limit: int = QueryParam(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    preds = list(db.scalars(
        select(DiseasePrediction).where(DiseasePrediction.user_id == user.id)
        .order_by(DiseasePrediction.created_at.desc()).limit(limit)
    ))
    lookup = _diseases_for(db, preds)
    return [_serialize(p, lookup) for p in preds]


@router.get("/classes", response_model=list[DiseaseInfoOut])
def classes(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """All diseases the system has information for (the disease library)."""
    return list(db.scalars(select(Disease).order_by(Disease.crop, Disease.disease_name)))


@router.get("/images/{filename}")
def get_image(filename: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    path = safe_child(settings.image_dir, filename)
    # Match on the unique file name, not the full path: Windows can write the same folder
    # as a short "8.3" path (C:\Users\P2B0~1.SIV\...) or a long one, so full paths may differ.
    owner = db.scalars(
        select(DiseasePrediction.user_id).where(DiseasePrediction.image_path.endswith(path.name))
    ).first()
    if owner is None or (owner != user.id and not user.is_admin):
        raise NotFoundError("Image not found")
    return FileResponse(path)
