"""Show what the RAG pipeline sees for a question: translation, retrieved passages and rerank scores.
    python -m scripts.diagnose_rag "question" [language_code]
"""
import sys

from app.core.config import get_settings
from app.services.container import ServiceContainer
from app.services.translation.languages import DEFAULT_LANGUAGES

NLLB = {lang["code"]: lang["nllb_code"] for lang in DEFAULT_LANGUAGES}

question = sys.argv[1]
lang = sys.argv[2] if len(sys.argv) > 2 else "en"
s = ServiceContainer(get_settings())
english = s.translator.translate(question, NLLB[lang], "eng_Latn") if lang != "en" else question
print("ENGLISH QUERY:", english)
hits = s.vector_store.query(s.embedder.encode([english])[0], 20)
print(f"\nTop vector hits (cosine distance, lower = closer), {len(hits)} found:")
for h in hits[:5]:
    m = h["metadata"]
    print(f"  {h['distance']:.3f}  {m['title']} p.{m['page']}  | {h['text'][:90]!r}")
ranked = s.reranker.rerank(english, [{"id": h["id"], "text": h["text"], "meta": h} for h in hits])
cut = get_settings().RAG_MIN_RERANK_SCORE
print(f"\nAfter FlashRank (kept if score >= {cut}):")
for r in ranked[:5]:
    m = r["meta"]["metadata"]
    flag = "KEEP" if r["score"] >= cut else "drop"
    print(f"  {r['score']:.4f} {flag}  {m['title']} p.{m['page']}  | {r['text'][:90]!r}")
