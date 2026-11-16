"""Conversation tables: conversation_history -> queries -> responses -> feedback.

One conversation (a chat session) has many queries; each query has exactly one
response; a response can get one feedback row per user.
"""
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.language import Language


class Intent(Base):
    __tablename__ = "intents"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    description: Mapped[str] = mapped_column(String(255))


class ConversationHistory(TimestampMixin, Base):
    __tablename__ = "conversation_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    language_id: Mapped[int] = mapped_column(ForeignKey("languages.id", ondelete="RESTRICT"))
    title: Mapped[str] = mapped_column(String(200))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    language: Mapped[Language] = relationship(lazy="joined")
    queries: Mapped[list["Query"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan", order_by="Query.id"
    )


class Query(TimestampMixin, Base):
    """What the farmer asked, plus speech/language/intent metadata."""

    __tablename__ = "queries"
    __table_args__ = (CheckConstraint("input_mode IN ('voice', 'text')", name="input_mode_valid"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversation_history.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    language_id: Mapped[int] = mapped_column(ForeignKey("languages.id", ondelete="RESTRICT"), index=True)
    intent_id: Mapped[int | None] = mapped_column(ForeignKey("intents.id", ondelete="SET NULL"), index=True)
    input_mode: Mapped[str] = mapped_column(String(10))
    original_text: Mapped[str] = mapped_column(Text)
    english_text: Mapped[str] = mapped_column(Text)
    detected_language: Mapped[str | None] = mapped_column(String(8))
    language_confidence: Mapped[float | None] = mapped_column(Float)
    intent_confidence: Mapped[float | None] = mapped_column(Float)
    audio_path: Mapped[str | None] = mapped_column(String(255))
    audio_duration_sec: Mapped[float | None] = mapped_column(Float)

    conversation: Mapped[ConversationHistory] = relationship(back_populates="queries")
    language: Mapped[Language] = relationship(lazy="joined")
    intent: Mapped[Intent | None] = relationship(lazy="joined")
    response: Mapped["Response | None"] = relationship(
        back_populates="query", uselist=False, cascade="all, delete-orphan", lazy="joined"
    )


class Response(TimestampMixin, Base):
    """The assistant's answer, its sources and per-stage timings (ms)."""

    __tablename__ = "responses"

    id: Mapped[int] = mapped_column(primary_key=True)
    query_id: Mapped[int] = mapped_column(ForeignKey("queries.id", ondelete="CASCADE"), unique=True)
    answer_english: Mapped[str] = mapped_column(Text)
    answer_text: Mapped[str] = mapped_column(Text)  # in the farmer's language
    grounded: Mapped[bool] = mapped_column(Boolean)  # True when built from retrieved sources
    sources: Mapped[list] = mapped_column(JSONB, default=list)
    model_name: Mapped[str | None] = mapped_column(String(80))
    audio_path: Mapped[str | None] = mapped_column(String(255))
    timings_ms: Mapped[dict] = mapped_column(JSONB, default=dict)
    total_ms: Mapped[int | None] = mapped_column(Integer)

    query: Mapped[Query] = relationship(back_populates="response")
    feedback: Mapped[list["Feedback"]] = relationship(back_populates="response", cascade="all, delete-orphan")


class Feedback(TimestampMixin, Base):
    __tablename__ = "feedback"
    __table_args__ = (UniqueConstraint("response_id", "user_id", name="uq_feedback_response_user"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    response_id: Mapped[int] = mapped_column(ForeignKey("responses.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    is_helpful: Mapped[bool] = mapped_column(Boolean)
    comment: Mapped[str | None] = mapped_column(String(500))

    response: Mapped[Response] = relationship(back_populates="feedback")
