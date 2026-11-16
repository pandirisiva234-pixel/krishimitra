"""RQ1 - Speech recognition accuracy (WER, CER), language identification and speed.

Uses the SAME speech code as the app (backend/app/services/speech), so the numbers describe
what farmers actually get. Two configurations are compared:
  general  - Whisper medium only (language detected, Telugu prompt and script fix)
  app      - Whisper medium detects the language; the IIT Madras Telugu model writes Telugu

Input: data/stt_manifest.csv with columns  audio_path,language,reference
  audio_path  a recording (m4a, mp3, wav, webm...) relative to the CSV's folder
  reference   the exact words spoken, in the language's own script

    cd ml/evaluation
    python stt_eval.py --manifest data/stt_manifest.csv

WER is harsh for Telugu (one long word = one error), so CER is reported too.
"""
import argparse
import json
import sys
import tempfile
import time
import unicodedata
from pathlib import Path

import jiwer
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from app.core.config import PROJECT_ROOT, get_settings  # noqa: E402
from app.services.speech.audio_utils import convert_to_wav16k  # noqa: E402
from app.services.speech.whisper_stt import SpeechToText  # noqa: E402


def normalise(text: str) -> str:
    """Lower-case, NFC, drop punctuation; keep letters, digits and combining vowel signs."""
    text = unicodedata.normalize("NFC", str(text).lower())
    keep = [ch if (ch.isalnum() or ch.isspace() or unicodedata.category(ch).startswith("M")) else " " for ch in text]
    return " ".join("".join(keep).split())


def build(config: str, s) -> SpeechToText:
    cache = s.MODEL_CACHE_DIR / "whisper"
    langs = {} if config == "general" else {k: PROJECT_ROOT / v for k, v in s.WHISPER_LANGUAGE_MODELS.items()}
    return SpeechToText(s.WHISPER_MODEL_SIZE, s.WHISPER_DEVICE, s.WHISPER_COMPUTE_TYPE, cache,
                        s.WHISPER_BEAM_SIZE, language_models=langs)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default="data/stt_manifest.csv")
    ap.add_argument("--configs", nargs="+", default=["general", "app"], choices=["general", "app"])
    ap.add_argument("--out", default="results/stt", type=Path)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    s = get_settings()
    manifest = pd.read_csv(args.manifest)
    base = Path(args.manifest).resolve().parent

    tmp = Path(tempfile.mkdtemp())
    wavs = []
    for i, r in enumerate(manifest.itertuples()):
        src = Path(r.audio_path)
        src = src if src.is_absolute() else base / src
        if not src.exists():
            raise SystemExit(f"Recording not found: {src}")
        wavs.append(convert_to_wav16k(src, tmp / f"{i:03d}.wav"))

    rows = []
    for config in args.configs:
        stt = build(config, s)
        stt._load()  # load before timing, so loading time is not counted per clip
        if config == "app":
            stt.load_language_models()
        for r, wav in zip(manifest.itertuples(), wavs):
            start = time.perf_counter()
            res = stt.transcribe(wav, language=None, hint=r.language)  # same call as the app
            elapsed = time.perf_counter() - start
            ref, hyp = normalise(r.reference), normalise(res.text)
            rows.append({
                "config": config, "language": r.language, "audio": str(r.audio_path),
                "duration_s": round(res.duration_sec, 2), "detected_language": res.language,
                "lid_correct": res.language == r.language, "lid_prob": round(res.language_probability, 3),
                "wer": round(jiwer.wer(ref, hyp), 4), "cer": round(jiwer.cer(ref, hyp), 4),
                "seconds": round(elapsed, 2), "rtf": round(elapsed / max(res.duration_sec, 0.1), 3),
                "reference": r.reference, "hypothesis": res.text,
            })
            print(f"{config:8s} {r.language} WER={rows[-1]['wer']:.2f} CER={rows[-1]['cer']:.2f} "
                  f"lang={res.language} {elapsed:.1f}s  {res.text}")

    df = pd.DataFrame(rows)
    df.to_csv(args.out / "stt_details.csv", index=False, encoding="utf-8-sig")
    summary = df.groupby(["config", "language"]).agg(
        clips=("wer", "size"), wer=("wer", "mean"), cer=("cer", "mean"),
        language_id_accuracy=("lid_correct", "mean"), avg_seconds=("seconds", "mean"),
        real_time_factor=("rtf", "mean"),
    ).round(4).reset_index()
    summary.to_csv(args.out / "stt_summary.csv", index=False)
    (args.out / "stt_summary.md").write_text(summary.to_markdown(index=False), encoding="utf-8")
    (args.out / "config.json").write_text(json.dumps(
        {**vars(args), "whisper": s.WHISPER_MODEL_SIZE, "beam": s.WHISPER_BEAM_SIZE}, default=str, indent=2))
    print("\n" + summary.to_string(index=False))


if __name__ == "__main__":
    main()
