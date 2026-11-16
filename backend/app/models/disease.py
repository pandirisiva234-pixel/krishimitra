from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class Disease(Base):
    """Curated description/treatment for each class the model can predict.

    `class_label` must match a label in trained_models/disease_labels.json
    (e.g. "Tomato___Early_blight").
    """

    __tablename__ = "diseases"

    id: Mapped[int] = mapped_column(primary_key=True)
    class_label: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    crop: Mapped[str] = mapped_column(String(60), index=True)
    disease_name: Mapped[str] = mapped_column(String(120))
    is_healthy: Mapped[bool] = mapped_column(Boolean, default=False)
    pathogen_type: Mapped[str | None] = mapped_column(String(40))  # fungal, bacterial, viral, pest, none
    description: Mapped[str] = mapped_column(Text)
    symptoms: Mapped[str] = mapped_column(Text)
    treatment: Mapped[str] = mapped_column(Text)
    prevention: Mapped[str] = mapped_column(Text)


class DiseasePrediction(TimestampMixin, Base):
    __tablename__ = "disease_predictions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    disease_id: Mapped[int | None] = mapped_column(ForeignKey("diseases.id", ondelete="SET NULL"), index=True)
    predicted_label: Mapped[str] = mapped_column(String(120))
    confidence: Mapped[float] = mapped_column(Float)
    is_uncertain: Mapped[bool] = mapped_column(Boolean)
    top_predictions: Mapped[list] = mapped_column(JSONB, default=list)
    blur_score: Mapped[float | None] = mapped_column(Float)
    image_path: Mapped[str] = mapped_column(String(255))
    model_version: Mapped[str | None] = mapped_column(String(60))
    inference_ms: Mapped[int | None] = mapped_column(Integer)

    disease: Mapped[Disease | None] = relationship(lazy="joined")
