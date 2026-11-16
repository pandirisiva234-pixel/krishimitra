from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TranscriptionOut(BaseModel):
    text: str
    language_code: str  # language the app will use
    detected_language: str | None  # raw Whisper guess
    language_probability: float | None
    used_fallback_language: bool  # True when Whisper was unsure and the profile language was used
    duration_sec: float
    processing_ms: int
    audio_id: str  # pass back to /assistant/query to link the recording


class SourceOut(BaseModel):
    index: int
    title: str
    page: int | None = None
    document_id: int | None = None
    score: float | None = None
    snippet: str
    kind: str = "document"  # document | weather


class AskRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    language_code: str | None = Field(default=None, max_length=8)
    conversation_id: int | None = None
    input_mode: str = Field(default="text", pattern="^(voice|text)$")
    audio_id: str | None = Field(default=None, max_length=64)
    speak: bool = False
    # The device's current position (browser location). Weather answers use it before the saved farm location.
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)


class AskResponse(BaseModel):
    conversation_id: int
    query_id: int
    response_id: int
    question: str
    question_english: str
    question_language: str  # detected language of the question
    language_code: str  # language of the answer
    intent: str
    intent_confidence: float | None
    answer: str
    answer_english: str
    grounded: bool
    sources: list[SourceOut]
    audio_url: str | None
    timings_ms: dict[str, int]


class SpeakRequest(BaseModel):
    text: str = Field(min_length=1, max_length=3000)
    language_code: str = Field(max_length=8)
    translate_from_english: bool = False


class TranslateRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)  # English text
    language_code: str = Field(max_length=8)


class FeedbackRequest(BaseModel):
    response_id: int
    is_helpful: bool
    comment: str | None = Field(default=None, max_length=500)


class MessageOut(BaseModel):
    query_id: int
    response_id: int | None
    question: str
    question_english: str
    answer: str | None
    answer_english: str | None
    intent: str | None
    input_mode: str
    grounded: bool | None
    sources: list[SourceOut]
    has_audio: bool
    audio_url: str | None
    created_at: datetime


class ConversationSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    language_code: str
    message_count: int
    created_at: datetime
    updated_at: datetime


class ConversationDetail(ConversationSummary):
    messages: list[MessageOut]


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=500)
    language_code: str | None = Field(default=None, max_length=8)
    top_n: int = Field(default=5, ge=1, le=10)


class KnowledgeSearchResponse(BaseModel):
    query_english: str
    results: list[SourceOut]
