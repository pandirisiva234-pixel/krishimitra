"""Creates every AI service once and shares it across requests.

Models load lazily (on first use) unless PRELOAD_MODELS=true. Routes get the
container through the `get_services` dependency, so tests can swap in fakes.
"""
import logging

from app.core.config import PROJECT_ROOT, Settings
from app.services.disease.predictor import DiseasePredictor
from app.services.llm.gemini_client import GeminiClient
from app.services.nlp.intent_classifier import IntentClassifier
from app.services.rag.embeddings import Embedder
from app.services.rag.reranker import Reranker
from app.services.rag.retriever import Retriever
from app.services.rag.vector_store import VectorStore
from app.services.speech.whisper_stt import SpeechToText
from app.services.translation.indictrans_translator import FallbackTranslator, IndicTransTranslator
from app.services.translation.nllb_translator import Translator
from app.services.tts.edge_tts_service import TextToSpeech
from app.services.weather.openweather_client import OpenWeatherClient
from app.services.weather.service import WeatherService

logger = logging.getLogger(__name__)


class ServiceContainer:
    def __init__(self, settings: Settings):
        s = settings
        self.settings = s
        cache = s.MODEL_CACHE_DIR
        self.stt = SpeechToText(
            s.WHISPER_MODEL_SIZE, s.WHISPER_DEVICE, s.WHISPER_COMPUTE_TYPE, cache, s.WHISPER_BEAM_SIZE,
            language_models={lang: PROJECT_ROOT / path for lang, path in s.WHISPER_LANGUAGE_MODELS.items()},
        )
        nllb = Translator(
            s.NLLB_MODEL, s.NLLB_BACKEND, cache,
            s.NLLB_CT2_PATH or str(PROJECT_ROOT / "trained_models" / "nllb-200-distilled-600M-ct2"), s.NLLB_BEAM_SIZE,
        )
        # AI4Bharat IndicTrans2 when chosen in .env, with NLLB as the automatic backup
        self.translator = (
            FallbackTranslator(IndicTransTranslator(cache, s.HF_TOKEN, s.NLLB_BEAM_SIZE), nllb)
            if s.TRANSLATION_ENGINE == "indictrans2" else nllb
        )
        self.embedder = Embedder(s.EMBEDDING_MODEL, cache)
        self.vector_store = VectorStore(s.CHROMA_DIR, s.CHROMA_COLLECTION)
        self.reranker = Reranker(s.RERANK_MODEL, cache) if s.RERANK_ENABLED else None
        self.retriever = Retriever(
            self.embedder,
            self.vector_store,
            self.reranker,
            top_k=s.RAG_TOP_K,
            top_n=s.RAG_TOP_N,
            min_rerank_score=s.RAG_MIN_RERANK_SCORE,
            max_distance=s.RAG_MAX_COSINE_DISTANCE,
        )
        self.intent = IntentClassifier(s.intent_model_path, self.embedder)
        self.llm = GeminiClient(s.GEMINI_API_KEY, s.GEMINI_MODEL, s.GEMINI_MAX_OUTPUT_TOKENS, s.GEMINI_THINKING_LEVEL)
        self.tts = TextToSpeech(s.tts_dir)
        self.disease = DiseasePredictor(s.disease_model_path, s.disease_labels_path)
        self.weather = WeatherService(OpenWeatherClient(s.OPENWEATHER_API_KEY), s.WEATHER_CACHE_MINUTES)

    def models_loaded(self) -> dict[str, bool]:
        return {
            "whisper": self.stt.is_loaded,
            "nllb": self.translator.is_loaded,
            "embeddings": self.embedder.is_loaded,
            "reranker": bool(self.reranker and self.reranker.is_loaded),
            "intent": self.intent.is_loaded,
            "disease": self.disease.is_loaded,
        }

    def preload(self) -> None:
        """Load everything now (slow start, fast first request). Failures are logged, not fatal."""
        steps = [
            ("whisper", lambda: self.stt._load()),
            ("whisper_language_models", lambda: self.stt.load_language_models()),
            ("nllb", lambda: self.translator._load()),
            ("embeddings", lambda: self.embedder._load()),
            ("reranker", lambda: self.reranker and self.reranker._load()),
            ("intent", lambda: self.intent.is_available and self.intent._load()),
            ("disease", lambda: self.disease.is_available and self.disease._load()),
        ]
        for name, step in steps:
            try:
                step()
                logger.info("Preloaded %s", name)
            except Exception:  # noqa: BLE001
                logger.exception("Could not preload %s", name)
