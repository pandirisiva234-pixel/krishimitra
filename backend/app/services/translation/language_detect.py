"""Text language detection by Unicode script.

Telugu, Kannada, Tamil, Malayalam, Bengali, Gujarati, Arabic (Urdu), Devanagari
(Hindi/Marathi) and Latin (English) each use their own alphabet, so counting which script most letters belong to identifies the
language almost exactly, and the result is easy to explain. Hindi and Marathi share
Devanagari, so the farmer's selected language decides between them.

Limitation (documented in the report): romanised text such as "pantaku
neeru eppudu pettali" is Latin script and is detected as English. In that case
the farmer's preferred language from their profile is used by the caller.
"""
from dataclasses import dataclass

from app.services.translation.languages import SCRIPT_RANGES


@dataclass
class DetectionResult:
    language_code: str | None  # None when nothing could be detected
    script: str | None
    confidence: float  # share of letters in the winning script (0..1)


def _script_of(char: str) -> str | None:
    cp = ord(char)
    for script, ranges in SCRIPT_RANGES.items():
        for lo, hi in ranges:
            if lo <= cp <= hi:
                return script
    return None


def detect_language(text: str, script_to_code: dict[str, str]) -> DetectionResult:
    """`script_to_code` maps a script to the active language using it, e.g. {"Telugu": "te"}."""
    counts: dict[str, int] = {}
    total = 0
    for ch in text:
        if not ch.isalpha() and not (0x0900 <= ord(ch) <= 0x0DFF):  # Indic vowel signs are not isalpha()
            continue
        script = _script_of(ch)
        if script is None:
            continue
        counts[script] = counts.get(script, 0) + 1
        total += 1

    if total == 0:
        return DetectionResult(None, None, 0.0)

    script, count = max(counts.items(), key=lambda kv: kv[1])
    return DetectionResult(script_to_code.get(script), script, round(count / total, 3))
