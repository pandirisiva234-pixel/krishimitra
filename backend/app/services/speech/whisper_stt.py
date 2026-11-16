"""Speech-to-text with Faster-Whisper.

The model is loaded once, on first use (a few seconds; the first run also
downloads it to trained_models/cache). Transcription returns the text and
Whisper's guess of the spoken language with a probability.
"""
import logging
import os
import threading
import time
import unicodedata
import wave
from dataclasses import dataclass
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)


def load_wav_16k_mono(path: Path) -> np.ndarray:
    """Read the 16 kHz mono 16-bit WAV produced by audio_utils.convert_to_wav16k as float32 in [-1, 1].

    Passing samples (not a file path) to Faster-Whisper skips its PyAV decoder, which avoids
    version clashes between faster-whisper and PyAV (e.g. "unexpected keyword 'metadata_errors'").
    """
    with wave.open(str(path), "rb") as wav:
        if wav.getframerate() != 16000 or wav.getnchannels() != 1 or wav.getsampwidth() != 2:
            raise ValueError("Expected 16 kHz mono 16-bit WAV; convert with convert_to_wav16k first")
        frames = wav.readframes(wav.getnframes())
    return np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0


# Unicode start of each Indic script block. Brahmic scripts share one 128-code-point layout, so a
# letter at offset k in the Devanagari or Kannada block is the same sound at offset k in Telugu's block.
_SCRIPT_BASE = {"hi": 0x0900, "mr": 0x0900, "bn": 0x0980, "pa": 0x0A00, "gu": 0x0A80, "or": 0x0B00,
                "ta": 0x0B80, "te": 0x0C00, "kn": 0x0C80, "ml": 0x0D00}
_INDIC = range(0x0900, 0x0D80)
_SHARED = {0x0964, 0x0965}  # danda marks are used by every Indic script

# A short sentence in the farmer's language and script, given to Whisper as "previous text".
# It steers Whisper to write in the right script and primes farming words (crops, pests, diseases).
SCRIPT_PROMPTS = {
    "te": "రైతు ప్రశ్న: టమాటా, మిరప, వరి, పత్తి, వేరుశనగ పంటలో ఆకులపై మచ్చలు, పురుగులు, తెగులు, ఎరువులు.",
    "hi": "किसान का सवाल: टमाटर, मिर्च, धान, कपास, मूंगफली की फसल में पत्तियों पर धब्बे, कीड़े, रोग, खाद।",
    "ta": "விவசாயி கேள்வி: தக்காளி, மிளகாய், நெல், பருத்தி, நிலக்கடலை பயிரில் இலைகளில் புள்ளிகள், பூச்சிகள், நோய், உரம்.",
    "kn": "ರೈತರ ಪ್ರಶ್ನೆ: ಟೊಮೇಟೊ, ಮೆಣಸಿನಕಾಯಿ, ಭತ್ತ, ಹತ್ತಿ, ಶೇಂಗಾ ಬೆಳೆಯಲ್ಲಿ ಎಲೆಗಳ ಮೇಲೆ ಕಲೆಗಳು, ಕೀಟಗಳು, ರೋಗ, ಗೊಬ್ಬರ.",
    "ml": "കർഷകന്റെ ചോദ്യം: തക്കാളി, മുളക്, നെല്ല്, പരുത്തി, നിലക്കടല വിളയിൽ ഇലകളിൽ പുള്ളികൾ, കീടങ്ങൾ, രോഗം, വളം.",
    "mr": "शेतकऱ्याचा प्रश्न: टोमॅटो, मिरची, भात, कापूस, भुईमूग पिकात पानांवर ठिपके, किडी, रोग, खत.",
    "bn": "কৃষকের প্রশ্ন: টমেটো, লঙ্কা, ধান, তুলা, চিনাবাদাম ফসলে পাতায় দাগ, পোকা, রোগ, সার।",
    "gu": "ખેડૂતનો પ્રશ્ન: ટામેટા, મરચાં, ડાંગર, કપાસ, મગફળી પાકમાં પાંદડા પર ડાઘ, જીવાત, રોગ, ખાતર.",
    "ur": "کسان کا سوال: ٹماٹر، مرچ، دھان، کپاس، مونگ پھلی کی فصل میں پتوں پر دھبے، کیڑے، بیماری، کھاد۔",
    "en": "Farmer question about tomato, chilli, paddy, cotton and groundnut: leaf spots, thrips, whitefly, blight, fertilizer.",
}


def fix_script(text: str, lang: str) -> str:
    """Whisper sometimes writes Telugu speech in another Indic script (Devanagari, Kannada...).

    When most letters belong to a different Indic script than the language's own, move each letter to
    the same position in the language's Unicode block. Letters with no counterpart are kept.
    """
    base = _SCRIPT_BASE.get(lang)
    if base is None:
        return text
    letters = [c for c in text if c.isalpha()]
    foreign = sum(1 for c in letters if ord(c) in _INDIC and not base <= ord(c) < base + 0x80)
    if not letters or foreign / len(letters) < 0.5:
        return text
    out = []
    for c in text:
        code = ord(c)
        if code in _INDIC and code not in _SHARED and not base <= code < base + 0x80:
            target = chr(base + (code - 0x0900) % 0x80)
            out.append(target if unicodedata.name(target, "") else c)
        else:
            out.append(c)
    return "".join(out)


INDIC_LANGS = {"te", "kn", "ta", "ml", "hi", "mr", "bn", "gu", "pa", "or", "ur"}  # Hindi/Urdu sound alike too
HINT_MIN_PROB = 0.05  # the selected language must still be a real possibility for Whisper


@dataclass
class TranscriptionResult:
    text: str
    language: str
    language_probability: float
    duration_sec: float
    hinted: bool = False  # True when the on-screen language choice overruled Whisper's guess


class SpeechToText:
    def __init__(
        self,
        model_size: str,
        device: str,
        compute_type: str,
        cache_dir: Path,
        beam_size: int = 1,
        language_models: dict[str, Path] | None = None,
    ):
        self.model_size = model_size
        # e.g. {"te": Path(".../whisper-telugu-small-ct2")}: fine-tuned models used only if the folder exists
        self.language_models = language_models or {}
        self._lang_loaded: dict[str, object] = {}
        self.beam_size = beam_size  # 1 = greedy decoding, several times faster on CPU than beam search
        self.device = device
        self.compute_type = compute_type
        self.cache_dir = cache_dir
        self._model = None
        self._lock = threading.Lock()

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    def _load(self):
        if self._model is None:
            with self._lock:
                if self._model is None:
                    from faster_whisper import WhisperModel  # heavy import, done lazily

                    logger.info("Loading Faster-Whisper '%s' on %s (%s)", self.model_size, self.device, self.compute_type)
                    self._model = WhisperModel(
                        self.model_size,
                        device=self.device,
                        compute_type=self.compute_type,
                        cpu_threads=os.cpu_count() or 4,
                        download_root=str(self.cache_dir / "whisper"),
                    )
        return self._model

    def _model_dir_ready(self, lang: str) -> Path | None:
        path = self.language_models.get(lang)
        return path if path and (path / "model.bin").exists() else None

    def _language_model(self, lang: str | None):
        """The fine-tuned model for this language, or None to use the general model."""
        if lang is None:
            return None
        if lang in self._lang_loaded:
            return self._lang_loaded[lang]
        path = self._model_dir_ready(lang)
        if path is None:
            return None
        with self._lock:
            if lang not in self._lang_loaded:
                from faster_whisper import WhisperModel

                logger.info("Loading fine-tuned '%s' Whisper model from %s", lang, path)
                self._lang_loaded[lang] = WhisperModel(
                    str(path), device=self.device, compute_type=self.compute_type, cpu_threads=os.cpu_count() or 4
                )
        return self._lang_loaded[lang]

    def load_language_models(self) -> None:
        for lang in self.language_models:
            self._language_model(lang)

    def transcribe(self, wav_path: Path, language: str | None = None, hint: str | None = None) -> TranscriptionResult:
        """`language=None` lets Whisper detect it; pass a code (e.g. "te") to force it.

        `hint` is the language selected on screen. Neighbouring Indian languages (Telugu and
        Kannada especially) sound alike, so when Whisper picks another Indian language but also
        gives the selected one a real chance, the farmer's selection wins.
        """
        model = self._load()
        started = time.perf_counter()
        audio = load_wav_16k_mono(wav_path)
        hinted = False
        if language is None:
            # Detect first, so we can give Whisper a prompt in the detected language's script.
            try:
                language, probability, all_probs = model.detect_language(audio, vad_filter=True)
            except ValueError:  # VAD found no speech at all; detect on the raw audio instead
                language, probability, all_probs = model.detect_language(audio)
            if hint and hint != language and hint in INDIC_LANGS and language in INDIC_LANGS:
                hint_prob = dict(all_probs).get(hint, 0.0)
                if hint_prob >= HINT_MIN_PROB:
                    logger.info("Using selected language %s (%.2f) instead of detected %s (%.2f)",
                                hint, hint_prob, language, probability)
                    language, probability, hinted = hint, hint_prob, True
        else:
            probability = 1.0
        # A model fine-tuned on this language (e.g. Telugu) is far more accurate than the general one.
        special = self._language_model(language)
        decoder = special or model
        segments, info = decoder.transcribe(
            audio,
            language=language,
            # the fine-tuned models were trained without prompts, so only the general model gets one
            initial_prompt=None if special else SCRIPT_PROMPTS.get(language),
            beam_size=self.beam_size,
            vad_filter=True,  # skip silence, reduces hallucinated text on quiet audio
            condition_on_previous_text=False,
            # One decoding pass only. By default Whisper re-decodes the whole clip up to 5 more times
            # at higher "temperatures" when it suspects repetition; for Telugu on a CPU that made a
            # 7-second clip take 2.5 minutes and still return a poor result.
            temperature=0.0,
            without_timestamps=True,  # we only need the text, not word timings
        )
        text = " ".join(seg.text.strip() for seg in segments).strip()  # decoding happens here (lazy generator)
        fixed = fix_script(text, language)
        if fixed != text:
            logger.info("Converted the transcript to the %s script", language)
            text = fixed
        logger.info(
            "Transcribed %.1fs of audio in %.1fs (lang=%s %.2f, model=%s, beam=%d)",
            info.duration, time.perf_counter() - started, language, probability,
            f"fine-tuned-{language}" if special else self.model_size, self.beam_size,
        )
        return TranscriptionResult(
            hinted=hinted,
            text=text,
            language=language,
            language_probability=float(probability),
            duration_sec=float(info.duration),
        )
