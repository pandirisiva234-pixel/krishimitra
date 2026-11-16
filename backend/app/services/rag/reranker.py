"""FlashRank reranking: a small cross-encoder that re-scores (query, passage) pairs on CPU.

Vector search finds passages that look similar; the cross-encoder reads the
question and passage together, so it is better at judging which actually answer it.
"""
import logging
import threading
from pathlib import Path

logger = logging.getLogger(__name__)


class Reranker:
    def __init__(self, model_name: str, cache_dir: Path):
        self.model_name = model_name
        self.cache_dir = cache_dir
        self._ranker = None
        self._lock = threading.Lock()

    @property
    def is_loaded(self) -> bool:
        return self._ranker is not None

    def _load(self):
        if self._ranker is None:
            with self._lock:
                if self._ranker is None:
                    from flashrank import Ranker

                    logger.info("Loading FlashRank model %s", self.model_name)
                    self._ranker = Ranker(model_name=self.model_name, cache_dir=str(self.cache_dir / "flashrank"))
        return self._ranker

    def rerank(self, query: str, passages: list[dict]) -> list[dict]:
        """passages: [{"id", "text", "meta"}] -> same dicts with "score", best first."""
        if not passages:
            return []
        from flashrank import RerankRequest

        results = self._load().rerank(RerankRequest(query=query, passages=passages))
        return [{**r, "score": float(r["score"])} for r in results]
