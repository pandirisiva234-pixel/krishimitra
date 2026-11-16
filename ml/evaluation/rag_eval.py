"""RQ2 + RQ3 — Retrieval evaluation on the indexed knowledge base.

CSV columns: question,language,question_en,relevant
  - `question` in the farmer's language, `question_en` its English version (human-written),
  - `relevant`: a short phrase that must appear in a correct passage (e.g. "gypsum"), or
    several alternatives separated by "|".

    python rag_eval.py            (reads data/rag_questions.csv)

Configurations compared (all on the same ChromaDB chunks):
  A  pivot:        human English question -> all-MiniLM-L6-v2 -> top-k
  B  pivot+rerank: A + FlashRank reranking                             (RQ3: B vs A)
  C  multilingual: native question -> paraphrase-multilingual-MiniLM   (RQ2: A vs C)
  D  app, no glossary:  native question -> NLLB -> MiniLM -> FlashRank
  E  app, glossary:     D + farming-glossary query expansion          (glossary effect: E vs D)
  F  app (as deployed): E + Gemini rewrites the question in English   (LLM effect: F vs E; needs GEMINI_API_KEY)
Metrics: hit@1, hit@3, hit@5, MRR@10.
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from app.core.config import get_settings  # noqa: E402
from app.services.rag.embeddings import Embedder  # noqa: E402
from app.services.rag.reranker import Reranker  # noqa: E402
from app.services.rag.vector_store import VectorStore  # noqa: E402
from app.core.config import PROJECT_ROOT  # noqa: E402
from app.services.llm.gemini_client import GeminiClient  # noqa: E402
from app.services.llm.prompts import (  # noqa: E402
    QUERY_REFINE_SYSTEM_PROMPT,
    build_query_refine_prompt,
    clean_refined_query,
)
from app.services.nlp.glossary import expand_query, glossary_terms  # noqa: E402
from app.services.translation.languages import DEFAULT_LANGUAGES  # noqa: E402
from app.services.translation.nllb_translator import Translator  # noqa: E402

MULTILINGUAL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
RATE_PAUSE_S = 5.0  # Gemini free tier allows 15 requests per minute; 5 s apart keeps us under it


def is_relevant(text: str, relevant: str) -> bool:
    return any(p.strip().lower() in text.lower() for p in str(relevant).split("|"))


def score(ranked_texts: list[list[str]], relevants: list[str]) -> dict:
    hits = {1: 0, 3: 0, 5: 0}
    rr = 0.0
    for texts, rel in zip(ranked_texts, relevants):
        first = next((i for i, t in enumerate(texts[:10], start=1) if is_relevant(t, rel)), None)
        for k in hits:
            hits[k] += int(first is not None and first <= k)
        rr += 1 / first if first else 0
    n = len(relevants)
    return {**{f"hit@{k}": round(v / n, 4) for k, v in hits.items()}, "MRR@10": round(rr / n, 4), "questions": n}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--questions", default="data/rag_questions.csv")
    ap.add_argument("--out", default="results/rag", type=Path)
    ap.add_argument("--top-k", type=int, default=20)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    s = get_settings()
    q = pd.read_csv(args.questions)

    store = VectorStore(s.CHROMA_DIR, s.CHROMA_COLLECTION)
    all_chunks = store._get().get(include=["documents", "metadatas"])
    print(f"Evaluating against {len(all_chunks['ids'])} indexed chunks")
    if not all_chunks["ids"]:
        raise SystemExit("Knowledge base is empty. Index documents first (scripts/ingest_documents.py).")

    english = Embedder(s.EMBEDDING_MODEL, s.MODEL_CACHE_DIR)
    results = {}

    # A: pivot (production setting without reranking)
    a_lists = []
    for text in q["question_en"]:
        hits = store.query(english.encode([text])[0], args.top_k)
        a_lists.append([h["text"] for h in hits])
    results["A_pivot_minilm"] = score(a_lists, q["relevant"].tolist())

    # B: pivot + FlashRank
    rr = Reranker(s.RERANK_MODEL, s.MODEL_CACHE_DIR)
    b_lists = []
    for text, cands in zip(q["question_en"], a_lists):
        ranked = rr.rerank(text, [{"id": str(i), "text": t} for i, t in enumerate(cands)])
        b_lists.append([r["text"] for r in ranked])
    results["B_pivot_minilm_flashrank"] = score(b_lists, q["relevant"].tolist())

    # C: multilingual embeddings on native-language questions (separate in-memory index)
    import chromadb

    multi = Embedder(MULTILINGUAL, s.MODEL_CACHE_DIR)
    client = chromadb.EphemeralClient()
    col = client.create_collection("multi_eval", metadata={"hnsw:space": "cosine"}, embedding_function=None)
    docs = all_chunks["documents"]
    for i in range(0, len(docs), 256):
        col.add(ids=all_chunks["ids"][i:i + 256], documents=docs[i:i + 256],
                embeddings=multi.encode(docs[i:i + 256]))
    c_lists = []
    for text in q["question"]:
        res = col.query(query_embeddings=[multi.encode([text])[0]], n_results=min(args.top_k, len(docs)))
        c_lists.append(res["documents"][0])
    results["C_native_multilingual"] = score(c_lists, q["relevant"].tolist())

    # D and E: what the app does with the farmer's own words
    nllb = {lang["code"]: lang["nllb_code"] for lang in DEFAULT_LANGUAGES}
    ct2 = s.NLLB_CT2_PATH or str(PROJECT_ROOT / "trained_models" / "nllb-200-distilled-600M-ct2")
    tr = Translator(s.NLLB_MODEL, s.NLLB_BACKEND, s.MODEL_CACHE_DIR, ct2, s.NLLB_BEAM_SIZE)

    names = {lang["code"]: lang["name"] for lang in DEFAULT_LANGUAGES}
    llm = GeminiClient(s.GEMINI_API_KEY, s.GEMINI_MODEL, s.GEMINI_MAX_OUTPUT_TOKENS, s.GEMINI_THINKING_LEVEL)

    import asyncio

    async def refine_all(items):
        # one event loop for all calls (the async Gemini client must not be reused across loops)
        out = []
        for text, lang, en in items:
            if lang == "en":
                out.append(en)
                continue
            prompt = build_query_refine_prompt(text, names.get(lang, lang), en, glossary_terms(text, lang))
            for attempt in range(4):
                try:
                    out.append(clean_refined_query(await llm.generate(prompt, QUERY_REFINE_SYSTEM_PROMPT), en))
                    break
                except Exception as exc:  # noqa: BLE001  - free tier: 15 requests per minute
                    if attempt == 3:
                        raise
                    print(f"Gemini busy ({exc}); waiting 60 s before retrying...")
                    await asyncio.sleep(60)
            await asyncio.sleep(RATE_PAUSE_S)  # stay under the free-tier limit
        return out

    def app_lists(use_glossary: bool, use_llm: bool = False):
        import asyncio

        queries = []
        for text, lang in zip(q["question"], q["language"]):
            en = text if lang == "en" else tr.translate(text, nllb[lang], "eng_Latn")
            if use_glossary:
                en = expand_query(en, text, lang)
            queries.append(en)
        if use_llm:
            queries = asyncio.run(refine_all(list(zip(q["question"], q["language"], queries))))
        lists = []
        for en in queries:
            cands = [h["text"] for h in store.query(english.encode([en])[0], args.top_k)]
            ranked = rr.rerank(en, [{"id": str(i), "text": c} for i, c in enumerate(cands)])
            lists.append([x["text"] for x in ranked])
        return lists, queries

    d_lists, d_queries = app_lists(False)
    e_lists, e_queries = app_lists(True)
    results["D_app_nllb_no_glossary"] = score(d_lists, q["relevant"].tolist())
    results["E_app_nllb_glossary"] = score(e_lists, q["relevant"].tolist())
    f_lists, f_queries = [], []
    if llm.is_configured:
        f_lists, f_queries = app_lists(True, use_llm=True)
        results["F_app_glossary_gemini"] = score(f_lists, q["relevant"].tolist())
    else:
        print("GEMINI_API_KEY not set: skipping configuration F")
    q.assign(nllb_query=d_queries, glossary_query=e_queries,
             gemini_query=f_queries or [""] * len(q)).to_csv(
        args.out / "app_queries.csv", index=False, encoding="utf-8-sig")

    table = pd.DataFrame(results).T.reset_index(names="configuration")
    table.to_csv(args.out / "retrieval_summary.csv", index=False)
    (args.out / "retrieval_summary.md").write_text(table.to_markdown(index=False))
    per_lang = []
    for lang, g in q.groupby("language"):
        idx = g.index.tolist()
        for name, lists in (("A", a_lists), ("B", b_lists), ("C", c_lists), ("D", d_lists), ("E", e_lists),
                            ("F", f_lists)):
            if not lists:
                continue
            per_lang.append({"language": lang, "config": name,
                             **score([lists[i] for i in idx], g["relevant"].tolist())})
    pd.DataFrame(per_lang).to_csv(args.out / "retrieval_by_language.csv", index=False)
    print(table.to_string(index=False))


if __name__ == "__main__":
    main()
