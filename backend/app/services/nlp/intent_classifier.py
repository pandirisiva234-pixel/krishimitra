"""Intent classification of the (English) question.

The trained model comes from ml/intent_classification/train_intent.py and is
saved as trained_models/intent_model.joblib, a dict:
    {"method": "tfidf" | "embedding", "pipeline": <sklearn model>,
     "labels": [...], "embedding_model": <name or None>, "metrics": {...}}

If the file does not exist yet (before Phase 9 training), a transparent keyword
fallback is used and every result says method="keywords", so reports never
confuse the two.
"""
import logging
import re
import threading
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

KEYWORDS: dict[str, list[str]] = {
    "weather": ["weather", "rain", "temperature", "forecast", "humidity", "wind", "hot", "cold", "monsoon", "cloud"],
    "pest_disease": ["pest", "insect", "disease", "worm", "borer", "fungus", "spots", "blight", "wilt", "rot",
                     "aphid", "whitefly", "white fly", "white flies", "flies", "mite", "thrips", "bollworm", "caterpillar", "leaf curl", "yellowing", "virus", "spray", "pesticide",
                     "insecticide", "fungicide"],
    "fertilizer_soil": ["fertilizer", "fertiliser", "urea", "dap", "potash", "manure", "compost", "soil",
                        "nitrogen", "phosphorus", "zinc", "npk", "nutrient", "deficiency", "ph"],
    "irrigation_water": ["irrigat", "water", "drip", "sprinkler", "watering", "moisture", "flood"],
    "harvest_storage": ["harvest", "storage", "store", "drying", "post-harvest", "godown", "yield", "mature"],
    "crop_cultivation": ["sow", "seed", "variety", "plant", "transplant", "spacing", "nursery", "cultivat",
                         "grow", "season", "kharif", "rabi", "crop"],
    "greeting": ["hello", "hi", "namaste", "thank", "thanks", "good morning", "good evening", "bye"],
}


# "Can I spray today?" is about the weather, not about a pest: timing + field work -> weather route
TIMING_WORDS = ("today", "tomorrow", "tonight", "this week", "next few days", "good day", "right now")
FIELD_WORK = ("spray", "pesticide", "insecticide", "fungicide", "fertilizer", "urea", "irrigat", "sow", "harvest")


@dataclass
class IntentResult:
    intent: str
    confidence: float | None
    method: str  # tfidf | embedding | keywords


def keyword_intent(text: str) -> IntentResult:
    lowered = text.lower()
    words = re.findall(r"[a-z\-]+", lowered)
    if any(t in lowered for t in TIMING_WORDS) and any(f in lowered for f in FIELD_WORK):
        return IntentResult("weather", None, "keywords")
    best, best_hits = "other", 0
    for intent, keys in KEYWORDS.items():
        hits = sum(1 for k in keys if (k in lowered if " " in k or len(k) > 4
                                       else k in words or f"{k}s" in words or f"{k}es" in words))
        if hits > best_hits:
            best, best_hits = intent, hits
    # A greeting word inside a real question should not win
    if best == "greeting" and len(words) > 6:
        return IntentResult("other", None, "keywords")
    return IntentResult(best, None, "keywords")


class IntentClassifier:
    def __init__(self, model_path: Path, embedder=None):
        self.model_path = model_path
        self.embedder = embedder
        self._bundle = None
        self._lock = threading.Lock()
        self._missing_logged = False

    @property
    def is_available(self) -> bool:
        return self.model_path.exists()

    @property
    def is_loaded(self) -> bool:
        return self._bundle is not None

    def _load(self):
        if self._bundle is None:
            with self._lock:
                if self._bundle is None:
                    import joblib

                    self._bundle = joblib.load(self.model_path)
                    logger.info("Loaded intent model (%s) from %s", self._bundle["method"], self.model_path)
        return self._bundle

    def predict(self, text_en: str) -> IntentResult:
        if not self.is_available:
            if not self._missing_logged:
                logger.warning("Intent model not found at %s; using keyword fallback", self.model_path)
                self._missing_logged = True
            return keyword_intent(text_en)

        bundle = self._load()
        pipeline = bundle["pipeline"]
        if bundle["method"] == "embedding":
            if self.embedder is None:
                return keyword_intent(text_en)
            features = self.embedder.encode([text_en])
        else:
            features = [text_en]
        probs = pipeline.predict_proba(features)[0]
        idx = int(probs.argmax())
        result = IntentResult(str(pipeline.classes_[idx]), float(probs[idx]), bundle["method"])
        # The model was trained on a few hundred questions; when it is unsure or says "other" but clear
        # farming words are present (e.g. "worms on maize leaves"), the keywords decide.
        if result.intent == "other" or (result.confidence or 0) < 0.5:
            kw = keyword_intent(text_en)
            if kw.intent not in ("other", "greeting"):
                return IntentResult(kw.intent, result.confidence, f"{bundle['method']}+keywords")
        return result
