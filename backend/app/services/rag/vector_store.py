"""ChromaDB wrapper (persistent, stored in knowledge_base/chroma_db).

We always pass our own embeddings, so Chroma never downloads its default model.
Each chunk's metadata: document_id, title, page, chunk_index.
"""
import logging
import threading
from pathlib import Path

logger = logging.getLogger(__name__)


class VectorStore:
    def __init__(self, persist_dir: Path, collection_name: str):
        self.persist_dir = persist_dir
        self.collection_name = collection_name
        self._collection = None
        self._lock = threading.Lock()

    def _get(self):
        if self._collection is None:
            with self._lock:
                if self._collection is None:
                    import chromadb
                    from chromadb.config import Settings as ChromaSettings

                    client = chromadb.PersistentClient(
                        path=str(self.persist_dir), settings=ChromaSettings(anonymized_telemetry=False)
                    )
                    self._collection = client.get_or_create_collection(
                        name=self.collection_name,
                        metadata={"hnsw:space": "cosine"},
                        embedding_function=None,
                    )
        return self._collection

    def add(self, ids: list[str], embeddings: list[list[float]], texts: list[str], metadatas: list[dict]) -> None:
        collection = self._get()
        batch = 500
        for i in range(0, len(ids), batch):
            collection.add(
                ids=ids[i : i + batch],
                embeddings=embeddings[i : i + batch],
                documents=texts[i : i + batch],
                metadatas=metadatas[i : i + batch],
            )

    def query(self, embedding: list[float], n_results: int) -> list[dict]:
        collection = self._get()
        if collection.count() == 0:
            return []
        res = collection.query(
            query_embeddings=[embedding],
            n_results=min(n_results, collection.count()),
            include=["documents", "metadatas", "distances"],
        )
        hits = []
        for chunk_id, text, meta, dist in zip(
            res["ids"][0], res["documents"][0], res["metadatas"][0], res["distances"][0]
        ):
            hits.append({"id": chunk_id, "text": text, "metadata": meta, "distance": float(dist)})
        return hits

    def delete_document(self, document_id: int) -> None:
        self._get().delete(where={"document_id": document_id})

    def count(self) -> int:
        return self._get().count()
