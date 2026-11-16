"""Find farming words the translator gets wrong in each language (round-trip check).

Each English test sentence contains one key farming word. The sentence is translated into the
language and back into English. If the key word (or an accepted synonym) is missing after the round
trip, the word was probably mistranslated, like "blight" -> "bulbul" (a bird) in Urdu.

Run from backend:
    python -m scripts.check_translations                   # NLLB, about 3-6 minutes
    python -m scripts.check_translations --engine gemini   # Gemini (what the app now uses), about 2 minutes
    python -m scripts.check_translations --engine indictrans2   # AI4Bharat IndicTrans2 (needs HF_TOKEN)
    python -m scripts.check_translations --languages ml bn gu
Output: ml/evaluation/results/translation_check_<engine>.csv, plus a list of problem words on screen.
With --engine gemini, Gemini translates all 30 sentences of a language in one request (and back), so
the free-tier limit of 15 requests a minute is not reached.
"""
import argparse
import asyncio
import csv
import json
import re
import time

from app.core.config import PROJECT_ROOT, get_settings
from app.services.translation.languages import DEFAULT_LANGUAGES
from app.services.llm.gemini_client import GeminiClient
from app.services.llm.prompts import build_translate_system_prompt
from app.services.translation.indictrans_translator import IndicTransTranslator
from app.services.translation.nllb_translator import Translator
from app.services.translation.post_edit import post_edit

ENGLISH = "eng_Latn"

# (key word, accepted words after the round trip, test sentence)
CHECKS = [
    ("blight", "blight|blast|scorch", "Early blight causes brown spots on old tomato leaves."),
    ("leaf spot", "leaf spot|spot", "Bacterial leaf spot makes small dark spots on chilli leaves."),
    ("powdery mildew", "mildew|powder", "Powdery mildew forms white powder on the leaves."),
    ("downy mildew", "mildew|mold|mould", "Downy mildew spreads fast in cool and wet weather."),
    ("rust", "rust", "Rust disease shows orange spots under the wheat leaves."),
    ("wilt", "wilt|wither|droop", "Fusarium wilt makes the whole plant droop and dry."),
    ("rot", "rot|decay", "Root rot happens when water stays in the field for long."),
    ("mosaic virus", "mosaic|virus", "Mosaic virus makes the leaves curl with yellow patches."),
    ("thrips", "thrip", "Thrips suck the sap from chilli leaves."),
    ("whitefly", "whitefl|white fl", "Whitefly spreads leaf curl virus in tomato."),
    ("aphids", "aphid|plant lice|lice", "Aphids gather on young shoots and suck the sap."),
    ("stem borer", "borer|bore", "Stem borer damages the paddy stem from inside."),
    ("caterpillar", "caterpillar|larva|worm", "Caterpillars eat holes in the cabbage leaves."),
    ("mites", "mite", "Red spider mites make the leaves look dusty and pale."),
    ("pest", "pest|insect", "Check the crop for pests every week."),
    ("fungicide", "fungicide|antifungal", "Spray a fungicide after removing the infected leaves."),
    ("insecticide", "insecticide|pesticide", "Use an insecticide only when the pests are many."),
    ("pesticide", "pesticide|insecticide", "Wear gloves and a mask when you spray any pesticide."),
    ("fertilizer", "fertili|manure", "Apply the fertilizer after the first weeding."),
    ("urea", "urea", "Apply urea in two split doses."),
    ("compost", "compost|manure", "Mix compost into the soil before sowing."),
    ("seedlings", "seedling|sapling|young plant", "Transplant the seedlings after twenty five days."),
    ("paddy", "paddy|rice", "Keep two centimetres of water in the paddy field."),
    ("groundnut", "groundnut|peanut", "Groundnut needs light soil with good drainage."),
    ("cotton", "cotton", "Pink bollworm is a serious pest of cotton."),
    ("chilli", "chil|pepper", "Chilli plants need water every four days in summer."),
    ("weeding", "weed", "Do the first weeding twenty days after sowing."),
    ("irrigation", "irrigat|water", "Avoid overhead irrigation to stop the disease spreading."),
    ("crop rotation", "rotat", "Crop rotation breaks the life cycle of soil diseases."),
    ("yellowing", "yellow", "Yellowing of lower leaves can mean nitrogen deficiency."),
]


class GeminiBatch:
    """Translates a whole list in one Gemini request (to stay under the free-tier rate limit)."""

    def __init__(self, settings):
        self.llm = GeminiClient(settings.GEMINI_API_KEY, settings.GEMINI_MODEL, 4096, settings.GEMINI_THINKING_LEVEL)

    def run(self, sentences: list[str], system: str) -> list[str]:
        prompt = ("Translate each item of this JSON list. Reply with a JSON list of the same length, "
                  "same order, translations only.\n" + json.dumps(sentences, ensure_ascii=False))
        out = asyncio.run(self.llm.generate(prompt, system, json_output=True, max_output_tokens=4096))
        items = json.loads(out)
        if not isinstance(items, list) or len(items) != len(sentences):
            raise ValueError("Gemini returned a list of the wrong length")
        return [str(x) for x in items]

    def to_language(self, sentences, lang_name):
        return self.run(sentences, build_translate_system_prompt(lang_name))

    def to_english(self, sentences, lang_name):
        return self.run(sentences, f"Translate from {lang_name} into plain English, word meaning as it is. "
                                   "Do not correct or improve the meaning.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--languages", nargs="*", default=["ml", "mr", "bn", "gu", "ur", "ta"])
    ap.add_argument("--engine", choices=["nllb", "gemini", "indictrans2"], default="nllb")
    args = ap.parse_args()
    settings = get_settings()

    gem = GeminiBatch(settings) if args.engine == "gemini" else None
    if args.engine == "indictrans2":
        t = IndicTransTranslator(settings.MODEL_CACHE_DIR, settings.HF_TOKEN, settings.NLLB_BEAM_SIZE)
    else:
        t = None if gem else Translator(settings.NLLB_MODEL, settings.NLLB_BACKEND, settings.MODEL_CACHE_DIR,
                   settings.NLLB_CT2_PATH or str(PROJECT_ROOT / "trained_models" / "nllb-200-distilled-600M-ct2"),
                   settings.NLLB_BEAM_SIZE)
    langs = {row["code"]: row for row in DEFAULT_LANGUAGES}
    out_path = PROJECT_ROOT / "ml" / "evaluation" / "results" / f"translation_check_{args.engine}.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    rows, problems = [], {}
    start = time.time()
    for code in args.languages:
        lang = langs[code]
        bad = 0
        sentences = [c[2] for c in CHECKS]
        if gem:
            for attempt in range(1, 4):  # Gemini is sometimes busy (error 503): wait and try again
                try:
                    locals_ = [post_edit(x, e, code) for x, e in zip(gem.to_language(sentences, lang["name"]), sentences)]
                    backs = gem.to_english(locals_, lang["name"])
                    break
                except Exception as exc:  # noqa: BLE001
                    print(f"  {lang['name']}: Gemini busy ({exc}); waiting 45 s (try {attempt}/3)")
                    time.sleep(45)
            else:
                print(f"{lang['name']:<10} skipped: Gemini unavailable, run again later with --languages {code}")
                continue
            time.sleep(8)  # stay well under 15 requests a minute
        else:
            locals_ = [post_edit(t.translate(e, ENGLISH, lang["nllb_code"]), e, code) for e in sentences]
            backs = [t.translate(x, lang["nllb_code"], ENGLISH) for x in locals_]
        for (word, accepted, sentence), local, back in zip(CHECKS, locals_, backs):
            ok = bool(re.search(accepted, back, re.I))
            bad += not ok
            rows.append({"language": code, "word": word, "ok": ok, "english": sentence,
                         "translated": local, "back_to_english": back})
            if not ok:
                problems.setdefault(code, []).append((word, back))
        print(f"{lang['name']:<10} {len(CHECKS) - bad}/{len(CHECKS)} key words survived ({args.engine})")

    if not rows:
        return
    with out_path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    print("\nProblem words (key word -> what came back):")
    for code, items in problems.items():
        for word, back in items:
            print(f"  [{code}] {word:<15} -> {back}")
    print(f"\nSaved {out_path}  ({time.time() - start:.0f} s)")


if __name__ == "__main__":
    main()
