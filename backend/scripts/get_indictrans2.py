"""Set up AI4Bharat IndicTrans2 (distilled 200M) and check that it works.

Before running:
  1. Log in on huggingface.co and click "Agree and access repository" on BOTH pages:
       https://huggingface.co/ai4bharat/indictrans2-en-indic-dist-200M
       https://huggingface.co/ai4bharat/indictrans2-indic-en-dist-200M
  2. Create a Read token (huggingface.co/settings/tokens) and add it to backend/.env:
       HF_TOKEN=hf_xxxxxxxx
  3. pip install indic-nlp-library sacremoses   (text processing, pure Python, works on Windows)

Run from backend:   python -m scripts.get_indictrans2
Downloads about 1 GB the first time, then translates a farming sentence in a few languages.
If everything prints OK, set TRANSLATION_ENGINE=indictrans2 in .env and restart the backend.
"""
import sys
import time

from app.core.config import get_settings
from app.services.translation.indictrans_translator import IndicTransTranslator, _processor

SENTENCE = "Early blight causes brown spots on old tomato leaves. Remove the infected leaves and spray a fungicide."
LANGS = {"te": "tel_Telu", "kn": "kan_Knda", "hi": "hin_Deva", "ml": "mal_Mlym", "ur": "urd_Arab"}


def main():
    s = get_settings()
    if not s.HF_TOKEN:
        sys.exit("HF_TOKEN is missing in backend/.env. See the steps at the top of this file.")
    try:
        _processor()
    except ImportError:
        sys.exit("Run first:  pip install indic-nlp-library sacremoses")

    t = IndicTransTranslator(s.MODEL_CACHE_DIR, s.HF_TOKEN, s.NLLB_BEAM_SIZE)
    start = time.time()
    try:
        t._load()
    except Exception as exc:  # noqa: BLE001
        msg = str(exc)
        if "401" in msg or "403" in msg or "gated" in msg.lower() or "access" in msg.lower():
            sys.exit("Hugging Face refused access. Click 'Agree' on BOTH model pages (same account as the "
                     f"token) and check HF_TOKEN.\nDetails: {msg[:300]}")
        raise
    print(f"Loaded both models in {time.time() - start:.0f} s\n")

    for code, tag in LANGS.items():
        t0 = time.time()
        local = t.translate(SENTENCE, "eng_Latn", tag)
        back = t.translate(local, tag, "eng_Latn")
        print(f"[{code}] {local}\n     back: {back}  ({time.time() - t0:.1f} s)\n")
    print("OK. Now compare engines:  python -m scripts.check_translations --engine indictrans2")
    print("To use it in the app: TRANSLATION_ENGINE=indictrans2 in .env, then restart the backend.")


if __name__ == "__main__":
    main()
