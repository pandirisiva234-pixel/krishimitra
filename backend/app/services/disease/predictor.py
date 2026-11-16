"""Disease prediction with the trained CNN exported to ONNX.

Files (produced by ml/disease_detection/src/export_onnx.py):
    trained_models/disease_model.onnx
    trained_models/disease_labels.json  {"labels": [...], "input_size": 224,
                                          "mean": [...], "std": [...], "model_name": ..., "version": ...}
"""
import json
import logging
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from app.core.exceptions import ServiceNotConfiguredError
from app.services.disease.preprocessing import blur_score, decode_image, preprocess

logger = logging.getLogger(__name__)

BLUR_THRESHOLD = 60.0  # below this the photo is probably out of focus


@dataclass
class Prediction:
    label: str
    confidence: float
    top: list[tuple[str, float]]
    blur: float
    inference_ms: int
    model_version: str | None


class DiseasePredictor:
    def __init__(self, model_path: Path, labels_path: Path):
        self.model_path = model_path
        self.labels_path = labels_path
        self._session = None
        self._meta: dict | None = None
        self._lock = threading.Lock()

    @property
    def is_available(self) -> bool:
        return self.model_path.exists() and self.labels_path.exists()

    @property
    def is_loaded(self) -> bool:
        return self._session is not None

    @property
    def labels(self) -> list[str]:
        self._load()
        return list(self._meta["labels"])

    def _load(self):
        if self._session is not None:
            return
        if not self.is_available:
            raise ServiceNotConfiguredError(
                "Disease model not found. Train it (ml/disease_detection) and copy disease_model.onnx "
                "and disease_labels.json into trained_models/."
            )
        with self._lock:
            if self._session is None:
                import onnxruntime as ort

                self._meta = json.loads(self.labels_path.read_text(encoding="utf-8"))
                self._session = ort.InferenceSession(str(self.model_path), providers=["CPUExecutionProvider"])
                logger.info("Loaded disease model %s (%s classes)", self._meta.get("version"), len(self._meta["labels"]))

    def predict(self, image_bytes: bytes, top_k: int = 3) -> Prediction:
        self._load()
        meta = self._meta
        rgb = decode_image(image_bytes)
        blur = blur_score(rgb)
        tensor = preprocess(
            rgb,
            size=int(meta.get("input_size", 224)),
            mean=meta.get("mean", [0.485, 0.456, 0.406]),
            std=meta.get("std", [0.229, 0.224, 0.225]),
        )
        start = time.perf_counter()
        input_name = self._session.get_inputs()[0].name
        logits = self._session.run(None, {input_name: tensor})[0][0].astype(np.float64)
        elapsed = int((time.perf_counter() - start) * 1000)

        logits = logits / float(meta.get("temperature", 1.0))  # temperature scaling (calibrate.py)
        exp = np.exp(logits - logits.max())  # numerically stable softmax
        probs = exp / exp.sum()
        order = np.argsort(probs)[::-1][:top_k]
        labels = meta["labels"]
        top = [(labels[i], float(probs[i])) for i in order]
        return Prediction(
            label=top[0][0],
            confidence=top[0][1],
            top=top,
            blur=blur,
            inference_ms=elapsed,
            model_version=meta.get("version"),
        )
