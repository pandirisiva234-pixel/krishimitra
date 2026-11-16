"""Farming glossary for query expansion.

NLLB is a general translator and gets farm words wrong: "తామర పురుగు" (thrips) comes out
as "lotus worm", "మిరప" (chilli) as "pepper". Retrieval then misses the right passages.
We look for known local terms in the ORIGINAL question and add the correct English terms to
the translated query, e.g. "How to prevent lotus worms in pepper? (thrips, chilli)".
Translation itself is untouched; only the search/intent query gets the extra words.

Terms are matched at the start of a word, so inflected forms also match
("పురుగుల" contains "పురుగు"). Longer phrases are checked first.
"""
import re

GLOSSARY: dict[str, dict[str, str]] = {
    "te": {
        "మొక్కజొన్న": "maize corn",
        "జొన్న": "sorghum jowar maize",
        "కత్తెర పురుగు": "fall armyworm",
        "తామర పురుగు": "thrips",
        "తెల్ల దోమ": "whitefly",
        "పచ్చ దోమ": "jassids leafhopper",
        "దోమ పోటు": "brown planthopper",
        "పేను బంక": "aphids",
        "కాయ తొలుచు పురుగు": "fruit borer",
        "కాండం తొలుచు పురుగు": "stem borer",
        "గులాబీ రంగు పురుగు": "pink bollworm",
        "పచ్చ పురుగు": "green caterpillar",
        "అగ్గి తెగులు": "blast disease",
        "ఆకు మచ్చ": "leaf spot",
        "ఆకు ముడత": "leaf curl",
        "ఎండు తెగులు": "wilt",
        "కుళ్ళు తెగులు": "rot",
        "బూజు తెగులు": "powdery mildew",
        "తెగులు": "disease",
        "పురుగు మందు": "pesticide",
        "పిచికారీ": "spray",
        "పిచికారి": "spray",
        "స్ప్రే": "spray",
        "ఈ రోజు": "today",
        "ఈరోజు": "today",
        "రేపు": "tomorrow",
        "వర్షం": "rain",
        "వాతావరణం": "weather",
        "ఎరువు": "fertilizer",
        "యూరియా": "urea",
        "ఊరియా": "urea",  # common speech-recognition spelling of urea
        "కలుపు": "weed",
        "మిరప": "chilli",
        "మిర్చి": "chilli",
        "టమాటా": "tomato",
        "టమోటా": "tomato",
        "పత్తి": "cotton",
        "వరి": "paddy rice",
        "వేరుశనగ": "groundnut",
        "వేరుశెనగ": "groundnut",
    },
    "kn": {
        "ಮೆಕ್ಕೆಜೋಳ": "maize corn",
        "ಮೆಕ್ಕೆ ಜೋಳ": "maize corn",
        "ಜೋಳ": "sorghum jowar maize",
        "ಸೈನಿಕ ಹುಳು": "fall armyworm",
        "ಕಂಬಳಿಹುಳು": "caterpillar",
        "ಹುಳು": "worm caterpillar",
        "ಎಲೆ ಚುಕ್ಕೆ": "leaf spot",
        "ಕೀಟನಾಶಕ": "pesticide",
        "ಸಿಂಪಡಣೆ": "spray",
        "ರಸಗೊಬ್ಬರ": "fertilizer",
        "ಗೊಬ್ಬರ": "fertilizer",
        "ಯೂರಿಯಾ": "urea",
        "ರೋಗ": "disease",
        "ಟೊಮೇಟೊ": "tomato",
        "ಟೊಮ್ಯಾಟೊ": "tomato",
        "ಮೆಣಸಿನಕಾಯಿ": "chilli",
        "ಭತ್ತ": "paddy rice",
        "ಹತ್ತಿ": "cotton",
        "ಶೇಂಗಾ": "groundnut",
        "ಕಡಲೆಕಾಯಿ": "groundnut",
    },
    "hi": {
        "मक्का": "maize corn",
        "ज्वार": "sorghum jowar maize",
        "फॉल आर्मीवर्म": "fall armyworm",
        "सैनिक कीट": "fall armyworm",
        "सफेद मक्खी": "whitefly",
        "थ्रिप्स": "thrips",
        "माहू": "aphids",
        "तना छेदक": "stem borer",
        "फल छेदक": "fruit borer",
        "गुलाबी सुंडी": "pink bollworm",
        "झुलसा": "blight",
        "कीटनाशक": "pesticide",
        "छिड़काव": "spray",
        "आज": "today",
        "कल": "tomorrow",
        "बारिश": "rain",
        "मौसम": "weather",
        "यूरिया": "urea",
        "खाद": "fertilizer",
        "मिर्च": "chilli",
        "टमाटर": "tomato",
        "कपास": "cotton",
        "धान": "paddy rice",
        "मूंगफली": "groundnut",
    },
}

_PATTERNS = {
    lang: [(re.compile(r"(?<!\S)" + re.escape(term)), english, term)
           for term, english in sorted(terms.items(), key=lambda kv: -len(kv[0]))]
    for lang, terms in GLOSSARY.items()
}


def _distance(a: str, b: str) -> int:
    """Levenshtein edit distance (small strings only)."""
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


FUZZY_MIN_LEN = 6  # only longer phrases get 1-edit tolerance; short words must match exactly


def _fuzzy_find(words: list[str], term: str) -> int | None:
    """Index of the first run of words that starts like `term` with at most one edit.

    Speech recognition sometimes changes one letter ("తామల పురుగుల" for "తామర పురుగుల").
    The words may carry endings, so the term is compared with prefixes of nearly its length.
    """
    k = len(term.split())
    for i in range(len(words) - k + 1):
        candidate = " ".join(words[i:i + k])
        n = len(term)
        if any(_distance(candidate[:m], term) <= 1 for m in (n - 1, n, n + 1) if 0 < m <= len(candidate)):
            return i
    return None


def glossary_terms(text: str, lang: str) -> list[str]:
    """English farm terms for local words found in `text` (in order, without duplicates)."""
    found: list[str] = []
    remaining = text
    for pattern, english, plain in _PATTERNS.get(lang, []):
        hit = bool(pattern.search(remaining))
        if hit:
            remaining = pattern.sub(" ", remaining)  # so "తెగులు" is not counted again inside "అగ్గి తెగులు"
        else:
            if len(plain.replace(" ", "")) >= FUZZY_MIN_LEN:
                words = remaining.split()
                i = _fuzzy_find(words, plain)
                if i is not None:
                    hit = True
                    k = len(plain.split())
                    remaining = " ".join(words[:i] + words[i + k:])
        if not hit:
            # speech recognition often splits or joins words: "వేరు శనగ" = "వేరుశనగ", "పురుగుమందు" = "పురుగు మందు"
            joined = plain.replace(" ", "")
            if len(joined) >= FUZZY_MIN_LEN and joined in remaining.replace(" ", ""):
                hit = True
        if hit and english not in found:
            found.append(english)
    return found


def expand_query(english: str, original: str, lang: str) -> str:
    """Add missing English farm terms to a translated question."""
    extra = [t for t in glossary_terms(original, lang) if t.lower() not in english.lower()]
    return f"{english} ({', '.join(extra)})" if extra else english
