"""Make translation about 3-4x faster on CPU: convert NLLB-200 to CTranslate2 int8.

    cd backend
    python -m scripts.get_fast_translator

Uses the NLLB model already downloaded in trained_models/cache (no second 2.4 GB download),
writes trained_models/nllb-200-distilled-600M-ct2 (about 600 MB), switches backend/.env to
it (NLLB_BACKEND=ctranslate2 and NLLB_CT2_PATH), and checks it with a real translation.
Restart the backend afterwards.
"""
import re
import time

from app.core.config import BACKEND_DIR, PROJECT_ROOT, get_settings

OUT = PROJECT_ROOT / "trained_models" / "nllb-200-distilled-600M-ct2"


def set_env(lines: list[str], key: str, value: str) -> list[str]:
    pattern = re.compile(rf"^\s*{key}\s*=")
    for i, line in enumerate(lines):
        if pattern.match(line):
            lines[i] = f"{key}={value}"
            return lines
    return [*lines, f"{key}={value}"]


def main() -> None:
    from ctranslate2.converters import TransformersConverter
    from huggingface_hub import snapshot_download

    settings = get_settings()
    cache = settings.MODEL_CACHE_DIR / "huggingface"
    print(f"Finding {settings.NLLB_MODEL} in {cache} (downloads only if missing)...")
    local = snapshot_download(settings.NLLB_MODEL, cache_dir=str(cache))
    print("Converting to CTranslate2 int8 (2-5 minutes)...")
    TransformersConverter(local).convert(str(OUT), quantization="int8", force=True)

    env = BACKEND_DIR / ".env"
    lines = env.read_text(encoding="utf-8").splitlines()
    lines = set_env(lines, "NLLB_BACKEND", "ctranslate2")
    lines = set_env(lines, "NLLB_CT2_PATH", str(OUT))
    env.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Updated {env}: NLLB_BACKEND=ctranslate2, NLLB_CT2_PATH={OUT}")

    from app.services.translation.nllb_translator import Translator

    tr = Translator(settings.NLLB_MODEL, "ctranslate2", settings.MODEL_CACHE_DIR, str(OUT), settings.NLLB_BEAM_SIZE)
    text = "Remove the lower infected leaves.\nSpray at the label rate every 10 to 14 days."
    start = time.perf_counter()
    out = tr.translate(text, "eng_Latn", "tel_Telu")
    print(f"Test translation ({time.perf_counter() - start:.1f}s, includes loading):\n{out}")
    print("OK. Restart the backend to use the fast translator.")


if __name__ == "__main__":
    main()
