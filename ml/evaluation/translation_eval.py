"""Translation quality of NLLB-200 (chrF++ and BLEU with sacrebleu), both directions.

CSV columns: language,source,reference_en
  - `source` is a farmer-style question in the language, `reference_en` a human English translation.
  - Use 20–50 sentences per language, translated by a fluent speaker (not by a machine).

    python translation_eval.py --data data/translation_testset.csv --out results/translation
Use --backend transformers to measure the full PyTorch model and compare it with the int8 model.
"""
import argparse
import sys
import time
from pathlib import Path

import pandas as pd
import sacrebleu

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
from app.core.config import PROJECT_ROOT, get_settings  # noqa: E402
from app.services.translation.languages import DEFAULT_LANGUAGES  # noqa: E402
from app.services.translation.nllb_translator import Translator  # noqa: E402

NLLB = {lang["code"]: lang["nllb_code"] for lang in DEFAULT_LANGUAGES}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/translation_testset.csv")
    ap.add_argument("--backend", default="auto", help="auto = the app's setting (int8 CTranslate2 if converted)")
    ap.add_argument("--out", default="results/translation", type=Path)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(args.data)
    st = get_settings()
    ct2 = st.NLLB_CT2_PATH or str(PROJECT_ROOT / "trained_models" / "nllb-200-distilled-600M-ct2")
    tr = Translator(st.NLLB_MODEL, args.backend, st.MODEL_CACHE_DIR, ct2, st.NLLB_BEAM_SIZE)
    print(f"Translator backend: {tr.backend}")

    rows = []
    for r in df.itertuples():
        start = time.perf_counter()
        to_en = tr.translate(r.source, NLLB[r.language], "eng_Latn")
        back = tr.translate(r.reference_en, "eng_Latn", NLLB[r.language])
        rows.append({"language": r.language, "source": r.source, "reference_en": r.reference_en,
                     "hyp_en": to_en, "hyp_back": back, "seconds": round(time.perf_counter() - start, 2)})
    out = pd.DataFrame(rows)
    out.to_csv(args.out / f"translation_details_{tr.backend}.csv", index=False, encoding="utf-8-sig")

    summary = []
    for lang, g in out.groupby("language"):
        chrf_en = sacrebleu.corpus_chrf(g.hyp_en.tolist(), [g.reference_en.tolist()], word_order=2).score
        bleu_en = sacrebleu.corpus_bleu(g.hyp_en.tolist(), [g.reference_en.tolist()]).score
        chrf_back = sacrebleu.corpus_chrf(g.hyp_back.tolist(), [g.source.tolist()], word_order=2).score
        summary.append({"language": lang, "sentences": len(g), "to_english_chrF++": round(chrf_en, 2),
                        "to_english_BLEU": round(bleu_en, 2), "from_english_chrF++": round(chrf_back, 2),
                        "avg_seconds_per_pair": round(g.seconds.mean(), 2)})
    s = pd.DataFrame(summary)
    s.to_csv(args.out / f"translation_summary_{tr.backend}.csv", index=False)
    print(s.to_string(index=False))
    print("Note: from_english chrF++ compares against the original question, which is a paraphrase-tolerant proxy.")


if __name__ == "__main__":
    main()
