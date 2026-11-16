"""Get a Whisper model fine-tuned on Telugu (or Kannada), in the CTranslate2 format faster-whisper needs.

    python scripts/get_telugu_whisper.py              # Telugu
    python scripts/get_telugu_whisper.py --lang kn    # Kannada (vasista22/whisper-kannada-small)
    --lang ta / hi / gu                               # Tamil, Hindi, Gujarati

Model: vasista22/whisper-telugu-small (Speech Lab, IIT Madras; Apache-2.0). It is Whisper
small fine-tuned on Telugu speech corpora, so it is both faster than Whisper medium and much
more accurate on Telugu. The general Whisper model is still used to detect the language;
this one is used only when the detected language is Telugu.

Step 1 converts the official model locally (int8). If that fails (for example a
transformers/ctranslate2 version mismatch), step 2 downloads a ready-made int8 conversion
of the same model (ukta-app/whisper-telugu-ct2). Either way the result is checked by
loading it with faster-whisper.

Output: trained_models/whisper-telugu-small-ct2/ or whisper-kannada-small-ct2/ (about 250 MB each).
Restart the backend after. Kannada has no ready-made conversion, so only step 1 is used for it.
"""
import argparse
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
# Speech Lab, IIT Madras fine-tunes of Whisper small (Apache-2.0)
MODELS = {
    "te": {"source": "vasista22/whisper-telugu-small", "prebuilt": "ukta-app/whisper-telugu-ct2",
           "out": "whisper-telugu-small-ct2"},
    "kn": {"source": "vasista22/whisper-kannada-small", "prebuilt": None, "out": "whisper-kannada-small-ct2"},
    "ta": {"source": "vasista22/whisper-tamil-small", "prebuilt": None, "out": "whisper-tamil-small-ct2"},
    "hi": {"source": "vasista22/whisper-hindi-small", "prebuilt": None, "out": "whisper-hindi-small-ct2"},
    "gu": {"source": "vasista22/whisper-gujarati-small", "prebuilt": None, "out": "whisper-gujarati-small-ct2"},
}
# Malayalam, Marathi, Bengali and Urdu have no IIT Madras "small" model; they use the general Whisper.
SOURCE_MODEL = MODELS["te"]["source"]
PREBUILT = MODELS["te"]["prebuilt"]


def convert(out: Path) -> None:
    from ctranslate2.converters import TransformersConverter

    print(f"Converting {SOURCE_MODEL} to CTranslate2 int8 (downloads about 1 GB the first time)...")
    TransformersConverter(SOURCE_MODEL).convert(str(out), quantization="int8", force=True)


def download_prebuilt(out: Path) -> None:
    from huggingface_hub import snapshot_download

    print(f"Downloading the ready-made conversion {PREBUILT}...")
    snapshot_download(PREBUILT, local_dir=str(out))


def ensure_side_files(out: Path) -> None:
    """faster-whisper reads tokenizer.json and preprocessor_config.json from the model folder."""
    from huggingface_hub import hf_hub_download

    for name in ("tokenizer.json", "preprocessor_config.json"):
        if (out / name).exists():
            continue
        for repo in (SOURCE_MODEL, "openai/whisper-small"):  # fine-tunes keep Whisper's vocabulary
            try:
                shutil.copy(hf_hub_download(repo, name), out / name)
                print(f"Added {name} from {repo}")
                break
            except Exception:  # noqa: BLE001
                continue


def verify(out: Path) -> None:
    from faster_whisper import WhisperModel

    WhisperModel(str(out), device="cpu", compute_type="int8")
    size_mb = sum(f.stat().st_size for f in out.rglob("*") if f.is_file()) / 1e6
    print(f"OK: faster-whisper loaded {out} ({size_mb:.0f} MB). Restart the backend to use it.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", choices=sorted(MODELS), default="te")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--prebuilt", action="store_true", help="skip conversion, download the ready-made model")
    args = ap.parse_args()
    global SOURCE_MODEL, PREBUILT
    SOURCE_MODEL, PREBUILT = MODELS[args.lang]["source"], MODELS[args.lang]["prebuilt"]
    args.out = args.out or PROJECT_ROOT / "trained_models" / MODELS[args.lang]["out"]
    args.out.mkdir(parents=True, exist_ok=True)

    done = False
    if not args.prebuilt:
        try:
            convert(args.out)
            done = True
        except Exception as exc:  # noqa: BLE001
            print(f"Conversion did not work ({type(exc).__name__}: {exc}). Trying the ready-made model.")
    if not done:
        if not PREBUILT:
            sys.exit("Conversion failed and there is no ready-made model for this language. Send this output for help.")
        download_prebuilt(args.out)
    ensure_side_files(args.out)
    if not (args.out / "model.bin").exists():
        sys.exit("model.bin is missing; the model was not created. Send this output for help.")
    verify(args.out)


if __name__ == "__main__":
    main()
