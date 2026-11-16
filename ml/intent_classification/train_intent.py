"""Intent classification experiment (Phase 9): TF-IDF baseline vs sentence-embedding model.

    cd ml/intent_classification
    python train_intent.py --data data/intents_seed.csv --out ../../trained_models/intent_model.joblib

Method:
  * fixed stratified 80/20 train/test split (seed 42),
  * 5-fold cross-validation on the training part to compare models,
  * final metrics on the untouched 20% test part,
  * the model with the best CV macro-F1 is saved for the backend.

The embedding model needs sentence-transformers and a one-time download of
all-MiniLM-L6-v2; if unavailable it is skipped and the report says so.

IMPORTANT: data/intents_seed.csv was written for development (240 questions). Before
reporting final results, add real farmer questions (e.g. from your own recordings or a
public Kisan Call Centre query dataset) and re-run this script. Say in the report which
data the numbers come from.
"""
import argparse
import json
from datetime import date
from pathlib import Path

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.feature_extraction.text import TfidfVectorizer  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.metrics import ConfusionMatrixDisplay, accuracy_score, classification_report, f1_score  # noqa: E402
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split  # noqa: E402
from sklearn.pipeline import FeatureUnion, make_pipeline  # noqa: E402

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


def tfidf_model():
    features = FeatureUnion([
        ("words", TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, min_df=1)),
        ("chars", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True, min_df=2)),
    ])
    return make_pipeline(features, LogisticRegression(max_iter=3000, C=5.0, class_weight="balanced"))


def embed(texts: list[str]):
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(EMBEDDING_MODEL, device="cpu")
    return model.encode(texts, normalize_embeddings=True, show_progress_bar=False)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/intents_seed.csv")
    ap.add_argument("--out", default="../../trained_models/intent_model.joblib")
    ap.add_argument("--results", default="results")
    ap.add_argument("--skip-embeddings", action="store_true")
    args = ap.parse_args()
    results = Path(args.results)
    results.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(args.data).dropna()
    df["text"] = df["text"].str.strip()
    df = df.drop_duplicates("text")
    X_train, X_test, y_train, y_test = train_test_split(
        df["text"].tolist(), df["label"].tolist(), test_size=0.2, stratify=df["label"], random_state=42
    )
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    report = {"data_file": args.data, "examples": len(df), "train": len(X_train), "test": len(X_test),
              "class_counts": df["label"].value_counts().to_dict(), "date": date.today().isoformat(), "models": {}}

    candidates = {}
    tfidf = tfidf_model()
    cv_scores = cross_val_score(tfidf, X_train, y_train, cv=cv, scoring="f1_macro")
    tfidf.fit(X_train, y_train)
    candidates["tfidf"] = (tfidf, X_test, cv_scores)

    if not args.skip_embeddings:
        try:
            E_train, E_test = embed(X_train), embed(X_test)
            emb = LogisticRegression(max_iter=3000, C=10.0, class_weight="balanced")
            cv_e = cross_val_score(emb, E_train, y_train, cv=cv, scoring="f1_macro")
            emb.fit(E_train, y_train)
            candidates["embedding"] = (emb, E_test, cv_e)
        except Exception as exc:  # noqa: BLE001
            report["embedding_skipped_reason"] = f"{type(exc).__name__}: {exc}"[:300]
            print(f"Embedding model skipped: {exc}")

    for name, (model, Xt, cvs) in candidates.items():
        pred = model.predict(Xt)
        report["models"][name] = {
            "cv_macro_f1_mean": round(float(np.mean(cvs)), 4), "cv_macro_f1_std": round(float(np.std(cvs)), 4),
            "test_accuracy": round(accuracy_score(y_test, pred), 4),
            "test_macro_f1": round(f1_score(y_test, pred, average="macro"), 4),
            "per_class": classification_report(y_test, pred, output_dict=True, zero_division=0),
        }
        fig, ax = plt.subplots(figsize=(7, 6))
        ConfusionMatrixDisplay.from_predictions(y_test, pred, ax=ax, xticks_rotation=45, cmap="Greens", colorbar=False)
        ax.set_title(f"Intent classifier ({name}) — test set, n={len(y_test)}")
        fig.tight_layout()
        fig.savefig(results / f"confusion_matrix_{name}.png", dpi=150)

    # Rule baseline: the backend's keyword fallback, scored on the same test split
    try:
        import sys

        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
        from app.services.nlp.intent_classifier import keyword_intent

        kw_pred = [keyword_intent(t).intent for t in X_test]
        report["models"]["keyword_rules"] = {
            "cv_macro_f1_mean": None, "cv_macro_f1_std": None,
            "test_accuracy": round(accuracy_score(y_test, kw_pred), 4),
            "test_macro_f1": round(f1_score(y_test, kw_pred, average="macro"), 4),
            "note": "Keywords and seed questions were written by the same author, so this score is likely optimistic.",
        }
        keyword_f1 = report["models"]["keyword_rules"]["test_macro_f1"]
    except ImportError:
        keyword_f1 = None

    best = max(candidates, key=lambda n: report["models"][n]["cv_macro_f1_mean"])
    if keyword_f1 is not None and report["models"][best]["test_macro_f1"] <= keyword_f1:
        report["selected"] = "keyword_rules"
        report["decision"] = (f"Best ML model ({best}, test macro-F1 {report['models'][best]['test_macro_f1']}) does not beat "
                              f"the keyword rules ({keyword_f1}). No model saved; the backend keeps using keyword rules. "
                              "Add more labelled questions and re-run.")
        Path(args.out).unlink(missing_ok=True)
        (results / "intent_report.json").write_text(json.dumps(report, indent=2))
        print(json.dumps({k: {m: v for m, v in r.items() if m != "per_class"} for k, r in report["models"].items()}, indent=2))
        print(report["decision"])
        return
    report["selected"] = best
    model = candidates[best][0]
    if best == "tfidf":
        model = tfidf_model().fit(df["text"].tolist(), df["label"].tolist())  # refit on all data for deployment
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"method": best, "pipeline": model, "labels": sorted(df["label"].unique()),
                 "embedding_model": EMBEDDING_MODEL if best == "embedding" else None,
                 "metrics": {k: {m: v for m, v in r.items() if m != "per_class"} for k, r in report["models"].items()},
                 "trained_on": args.data}, args.out)
    (results / "intent_report.json").write_text(json.dumps(report, indent=2))
    summary = {k: {m: v for m, v in r.items() if m != "per_class"} for k, r in report["models"].items()}
    print(json.dumps({"selected": best, "models": summary, "saved_to": args.out}, indent=2))


if __name__ == "__main__":
    main()
