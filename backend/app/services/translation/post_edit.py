"""Rule-based post-editing of translated answers.

NLLB is a general translator and gets some farm words wrong in answers, for example
"rice/paddy" -> బియ్యం (cooked/grain rice) instead of వరి (the crop), and "moths" -> మొసళ్ళు
(crocodiles). Each rule fires only when the English answer contains the trigger word, so a
correct use of the same Telugu word elsewhere is left alone. Rules come from errors observed
in testing; they are a stop-gap until the translation model is adapted to farming text.
"""
import re

# (language, English trigger regex, English words that cancel the rule, wrong text, right text)
RULES: list[tuple[str, str, str | None, str, str]] = [
    ("te", r"\b(rice|paddy)\b", None, "బియ్యం", "వరి"),
    ("te", r"\bmoths?\b", None, "మొసళ్ళ", "రెక్కల పురుగుల"),
    ("te", r"\bmoths?\b", None, "మొసళ్ల", "రెక్కల పురుగుల"),
    ("te", r"\bmoths?\b", None, "మొసలి", "రెక్కల పురుగు"),
    ("te", r"\b(predators?|natural enemies)\b", r"\b(livestock|cattle|cows?|buffalo|animals?)\b", "పశువుల", "మిత్ర పురుగుల"),
    ("te", r"\b(predators?|natural enemies)\b", r"\b(livestock|cattle|cows?|buffalo|animals?)\b", "పశువులు", "మిత్ర పురుగులు"),
    ("te", r"\bstraight fertili[sz]ers?\b", None, "సరళమైన ఎరువులు", "ఏక పోషక ఎరువులు"),
    ("te", r"\b(groundnuts?|peanuts?)\b", None, "మట్టి గింజల", "వేరుశనగ"),
    ("te", r"\b(groundnuts?|peanuts?)\b", None, "మట్టి గింజలు", "వేరుశనగ"),
    # Spelling: "app" is written अ + ॅ by the translator, which fonts show as a broken letter; Marathi uses ॲ
    ("mr", r".", None, "अॅ", "ॲ"),
    ("hi", r".", None, "अॅ", "ऍ"),
    # Kannada: "neem" is written as the English sound ನಿಮ್; farmers say ಬೇವು
    ("kn", r"\bneem\b", None, "ನಿಮ್ ಎಣ್ಣೆ", "ಬೇವಿನ ಎಣ್ಣೆ"),
    ("kn", r"\bneem\b", None, "ನಿಮ್ ", "ಬೇವಿನ "),
    # Kannada: "maize" comes out as ಮಧುಮೇಹ (diabetes); farmers say ಮೆಕ್ಕೆಜೋಳ
    ("kn", r"\b(maize|corn)\b", None, "ಮಧುಮೇಹ", "ಮೆಕ್ಕೆಜೋಳ"),
    # Urdu: the translator turns "blight" into "bulbul" (a songbird); farmers say jhulsa
    ("ur", r"\bblight\b", None, "بلبل", "جھلسا"),
]


def post_edit(translated: str, english: str, lang_code: str) -> str:
    out = translated
    for lang, trigger, cancel, wrong, right in RULES:
        if lang != lang_code or wrong not in out:
            continue
        if re.search(trigger, english, re.I) and not (cancel and re.search(cancel, english, re.I)):
            out = out.replace(wrong, right)
    return out
