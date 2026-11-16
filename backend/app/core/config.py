"""Application settings.

Every value is read from environment variables (or backend/.env).
Nothing secret is hard-coded: API keys and passwords have no defaults.
"""
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# krishimitra/backend/app/core/config.py -> parents[3] = krishimitra/
PROJECT_ROOT = Path(__file__).resolve().parents[3]
BACKEND_DIR = PROJECT_ROOT / "backend"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ---- General -------------------------------------------------------
    APP_NAME: str = "KrishiMitra API"
    ENVIRONMENT: str = "development"  # development | test | production
    API_PREFIX: str = "/api"
    LOG_LEVEL: str = "INFO"
    # NoDecode: read "a,b" as plain text and split it ourselves (see split_origins) instead of expecting JSON
    CORS_ORIGINS: Annotated[list[str], NoDecode] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # ---- Database ------------------------------------------------------
    DATABASE_URL: str = Field(
        ..., description="postgresql+psycopg://user:password@host:5432/dbname"
    )

    # ---- Security ------------------------------------------------------
    JWT_SECRET_KEY: str = Field(..., min_length=32)
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_LOGIN: str = "5/minute"
    RATE_LIMIT_AI: str = "20/minute"
    RATE_LIMIT_TTS: str = "60/minute"  # answers are spoken in several short pieces

    # ---- External APIs (optional: features report "not configured") -----
    GEMINI_API_KEY: str | None = None
    GEMINI_MODEL: str = "gemini-3.5-flash-lite"  # fastest; measured 3.7 s vs 43.7 s for gemini-3.6-flash
    GEMINI_MAX_OUTPUT_TOKENS: int = 600
    # How much Gemini "thinks" before answering: minimal | low | medium | high (empty = model default).
    # Answers are grounded in retrieved passages, so low thinking is enough and much faster.
    # When the documents have no answer: True = Gemini gives clearly-labelled general farming advice
    # (non-farming questions are still refused); False = always reply "not in the knowledge base".
    GENERAL_FARMING_FALLBACK: bool = True
    # Gemini checks NLLB's English version of a non-English question before searching
    # (fixes mistranslated farm words; about +3 s). False = NLLB + glossary only.
    QUERY_REFINE_WITH_LLM: bool = True
    # Answers in these languages are translated by Gemini instead of NLLB. A round-trip test showed NLLB
    # keeps only 62.8% of farming words in the newer languages (Gemini 96.7%; e.g. "blight" -> "bulbul"
    # in Urdu), and live Kannada tests turned caterpillars into cockroaches and moths into crocodiles.
    # NLLB stays the automatic backup if Gemini fails or is busy. Empty = NLLB for every language.
    LLM_TRANSLATE_LANGUAGES: list[str] = ["te", "hi", "kn", "ta", "ml", "mr", "bn", "gu", "ur"]
    GEMINI_THINKING_LEVEL: str | None = "minimal"
    OPENWEATHER_API_KEY: str | None = None
    WEATHER_CACHE_MINUTES: int = 30

    # ---- Speech ---------------------------------------------------------
    WHISPER_MODEL_SIZE: str = "small"  # tiny | base | small | medium | large-v3
    WHISPER_DEVICE: str = "cpu"  # cpu | cuda
    WHISPER_COMPUTE_TYPE: str = "int8"  # int8 on CPU, float16 on GPU
    WHISPER_MIN_LANGUAGE_PROB: float = 0.6
    WHISPER_BEAM_SIZE: int = 1  # 1 = fast greedy decoding on CPU; 5 = slightly more accurate, much slower
    # Language-specific fine-tuned Whisper models (CTranslate2 folders, relative to the project root).
    # Used for that language when the folder exists; the general model still detects the language.
    # Create them with: python scripts/get_telugu_whisper.py  (and --lang kn for Kannada)
    # A language without its folder simply uses the general model.
    WHISPER_LANGUAGE_MODELS: dict[str, str] = {
        "te": "trained_models/whisper-telugu-small-ct2",
        "kn": "trained_models/whisper-kannada-small-ct2",
        "ta": "trained_models/whisper-tamil-small-ct2",
        "hi": "trained_models/whisper-hindi-small-ct2",
        "gu": "trained_models/whisper-gujarati-small-ct2",
    }

    # ---- Translation ----------------------------------------------------
    # nllb = Meta NLLB-200 (default) | indictrans2 = AI4Bharat IndicTrans2 (NLLB stays the backup).
    # IndicTrans2 needs HF_TOKEN; set it up with: python scripts/get_indictrans2.py
    TRANSLATION_ENGINE: str = "nllb"
    HF_TOKEN: str | None = None
    NLLB_MODEL: str = "facebook/nllb-200-distilled-600M"
    NLLB_BACKEND: str = "auto"  # auto | transformers | ctranslate2 (auto = ctranslate2 if NLLB_CT2_PATH exists)
    NLLB_CT2_PATH: str | None = str(PROJECT_ROOT / "trained_models" / "nllb-200-distilled-600M-ct2")
    NLLB_BEAM_SIZE: int = 2  # 4 = slightly better wording, about 2x slower on CPU

    # ---- RAG -------------------------------------------------------------
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    RERANK_MODEL: str = "ms-marco-MiniLM-L-12-v2"
    RERANK_ENABLED: bool = True
    CHROMA_COLLECTION: str = "agri_knowledge"
    RAG_TOP_K: int = 20  # candidates from ChromaDB
    RAG_TOP_N: int = 5  # kept after reranking
    RAG_MIN_RERANK_SCORE: float = 0.05  # below this a chunk is "not relevant"
    RAG_MAX_COSINE_DISTANCE: float = 0.75  # used when reranking is disabled
    CHUNK_SIZE: int = 800
    CHUNK_OVERLAP: int = 150

    # ---- Disease model --------------------------------------------------
    DISEASE_CONFIDENCE_THRESHOLD: float = 0.60

    # ---- Upload limits --------------------------------------------------
    MAX_IMAGE_MB: int = 5
    MAX_AUDIO_MB: int = 10
    MAX_AUDIO_SECONDS: int = 60
    MAX_PDF_MB: int = 25

    # ---- Paths ------------------------------------------------------------
    STORAGE_DIR: Path = PROJECT_ROOT / "storage"
    CHROMA_DIR: Path = PROJECT_ROOT / "knowledge_base" / "chroma_db"
    MODELS_DIR: Path = PROJECT_ROOT / "trained_models"
    MODEL_CACHE_DIR: Path = PROJECT_ROOT / "trained_models" / "cache"

    # Load the AI models at startup instead of on first request
    PRELOAD_MODELS: bool = False

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def split_origins(cls, value):
        if isinstance(value, str) and not value.startswith("["):
            return [v.strip() for v in value.split(",") if v.strip()]
        return value

    # Derived paths -----------------------------------------------------
    @property
    def image_dir(self) -> Path:
        return self.STORAGE_DIR / "uploads" / "images"

    @property
    def audio_upload_dir(self) -> Path:
        return self.STORAGE_DIR / "uploads" / "audio"

    @property
    def document_dir(self) -> Path:
        return self.STORAGE_DIR / "uploads" / "documents"

    @property
    def tts_dir(self) -> Path:
        return self.STORAGE_DIR / "audio_responses"

    @property
    def disease_model_path(self) -> Path:
        return self.MODELS_DIR / "disease_model.onnx"

    @property
    def disease_labels_path(self) -> Path:
        return self.MODELS_DIR / "disease_labels.json"

    @property
    def intent_model_path(self) -> Path:
        return self.MODELS_DIR / "intent_model.joblib"

    def ensure_dirs(self) -> None:
        for path in (
            self.image_dir,
            self.audio_upload_dir,
            self.document_dir,
            self.tts_dir,
            self.CHROMA_DIR,
            self.MODELS_DIR,
            self.MODEL_CACHE_DIR,
        ):
            path.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()
