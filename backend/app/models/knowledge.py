from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class Document(TimestampMixin, Base):
    """A knowledge-base file. Its chunks/vectors live in ChromaDB, keyed by document id."""

    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint("status IN ('processing', 'indexed', 'failed')", name="status_valid"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    original_filename: Mapped[str] = mapped_column(String(255))
    stored_path: Mapped[str] = mapped_column(String(255))
    source_url: Mapped[str | None] = mapped_column(String(500))
    file_size_bytes: Mapped[int] = mapped_column(Integer)
    num_pages: Mapped[int | None] = mapped_column(Integer)
    num_chunks: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(12), default="processing")
    error_message: Mapped[str | None] = mapped_column(Text)
    uploaded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class WeatherData(Base):
    """Weather API responses, stored as a cache and for analysis."""

    __tablename__ = "weather_data"
    __table_args__ = (CheckConstraint("kind IN ('current', 'forecast')", name="kind_valid"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    kind: Mapped[str] = mapped_column(String(10))
    latitude: Mapped[float] = mapped_column(Float)  # rounded to 2 decimals (~1 km) for caching
    longitude: Mapped[float] = mapped_column(Float)
    location_name: Mapped[str | None] = mapped_column(String(120))
    payload: Mapped[dict] = mapped_column(JSONB)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
