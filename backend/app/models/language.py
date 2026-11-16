from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Language(Base):
    """A supported language. Adding a row (plus its voice) adds a language: no code change.

    code         ISO 639-1 code used across the app ("te")
    whisper_code language code Faster-Whisper uses ("te")
    nllb_code    NLLB-200 language tag ("tel_Telu")
    tts_voice    Edge-TTS neural voice ("te-IN-ShrutiNeural")
    script       Unicode script used for text language detection ("Telugu")
    """

    __tablename__ = "languages"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(8), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(50))
    native_name: Mapped[str] = mapped_column(String(50))
    whisper_code: Mapped[str] = mapped_column(String(8))
    nllb_code: Mapped[str] = mapped_column(String(16))
    tts_voice: Mapped[str] = mapped_column(String(64))
    script: Mapped[str] = mapped_column(String(32))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
