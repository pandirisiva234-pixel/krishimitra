"""Retrieval: embed the English query, take top-K from ChromaDB, rerank, keep top-N relevant chunks."""
import re
from dataclasses import dataclass


@dataclass
class RetrievedChunk:
    text: str
    title: str
    page: int | None
    document_id: int | None
    vector_distance: float
    rerank_score: float | None

    @property
    def score(self) -> float:
        return self.rerank_score if self.rerank_score is not None else round(1 - self.vector_distance, 4)


# Crop words in the (English) question -> word in the document titles. Jowar/sorghum use the maize
# documents (same pests, e.g. fall armyworm). Used to search again with the crop and rank its documents first.
CROP_TITLE_WORDS = {
    "maize": "maize", "corn": "maize", "sorghum": "maize", "jowar": "maize",
    "paddy": "rice", "rice": "rice",
    "cotton": "cotton",
    "chilli": "chilli", "chili": "chilli", "capsicum": "chilli",
    "tomato": "tomato",
    "groundnut": "groundnut", "peanut": "groundnut",
}
CROP_BOOST = 0.25


def crops_in(text: str) -> list[str]:
    """Title words of the crops named in the question, e.g. "worms on jowar leaves" -> ["maize"]."""
    words = re.findall(r"[a-z]+", text.lower())
    found: list[str] = []
    for w in words:
        forms = (w, w[:-1] if w.endswith("s") else w, w[:-2] if w.endswith("es") else w)  # chillies, tomatoes
        title = next((CROP_TITLE_WORDS[f] for f in forms if f in CROP_TITLE_WORDS), None)
        if title and title not in found:
            found.append(title)
    return found


class Retriever:
    def __init__(
        self,
        embedder,
        store,
        reranker=None,
        top_k: int = 20,
        top_n: int = 5,
        min_rerank_score: float = 0.05,
        max_distance: float = 0.75,
    ):
        self.embedder = embedder
        self.store = store
        self.reranker = reranker
        self.top_k = top_k
        self.top_n = top_n
        self.min_rerank_score = min_rerank_score
        self.max_distance = max_distance

    def retrieve(self, query_en: str, top_n: int | None = None, use_rerank: bool = True) -> list[RetrievedChunk]:
        top_n = top_n or self.top_n
        crops = crops_in(query_en)
        queries = [query_en] + [f"{crop} {query_en}" for crop in crops]
        vectors = self.embedder.encode(queries)
        hits, seen = [], set()
        for vec in vectors:  # the plain question, then once per named crop; merged without duplicates
            for h in self.store.query(vec, self.top_k):
                if h["id"] not in seen:
                    seen.add(h["id"])
                    hits.append(h)
        if not hits:
            return []

        def on_crop(chunk: "RetrievedChunk") -> bool:
            return any(c in chunk.title.lower() for c in crops)

        def to_chunk(hit: dict, score: float | None) -> RetrievedChunk:
            meta = hit["metadata"]
            page = meta.get("page")
            return RetrievedChunk(
                text=hit["text"],
                title=meta.get("title", "Untitled"),
                page=None if page in (None, -1) else int(page),
                document_id=meta.get("document_id"),
                vector_distance=hit["distance"],
                rerank_score=score,
            )

        if use_rerank and self.reranker is not None:
            passages = [{"id": h["id"], "text": h["text"], "meta": h} for h in hits]
            ranked = self.reranker.rerank(query_en, passages)
            chunks = [to_chunk(r["meta"], r["score"]) for r in ranked if r["score"] >= self.min_rerank_score]
            if crops:  # documents about the farmer's crop first
                chunks.sort(key=lambda c: (c.rerank_score or 0) + (CROP_BOOST if on_crop(c) else 0), reverse=True)
        else:
            chunks = [to_chunk(h, None) for h in hits if h["distance"] <= self.max_distance]
            chunks.sort(key=lambda c: c.vector_distance - (CROP_BOOST if crops and on_crop(c) else 0))
        return chunks[:top_n]
