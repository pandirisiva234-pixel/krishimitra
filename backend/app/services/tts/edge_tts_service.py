"""Text-to-speech with Edge-TTS (Microsoft neural voices; needs internet).

Audio files are cached by a hash of (voice, text): the same answer is never
synthesised twice. If Edge-TTS fails, gTTS is tried as a fallback.
"""
import hashlib
import logging
from pathlib import Path

from app.core.exceptions import ExternalServiceError

logger = logging.getLogger(__name__)


class TextToSpeech:
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _path_for(self, text: str, voice: str) -> Path:
        digest = hashlib.sha256(f"{voice}|{text}".encode("utf-8")).hexdigest()[:32]
        return self.output_dir / f"{digest}.mp3"

    async def synthesize(self, text: str, voice: str, gtts_lang: str | None = None) -> Path:
        path = self._path_for(text, voice)
        if path.exists() and path.stat().st_size > 0:
            return path
        try:
            import edge_tts

            await edge_tts.Communicate(text, voice).save(str(path))
            if path.stat().st_size == 0:
                raise RuntimeError("empty audio")
            return path
        except Exception as exc:  # noqa: BLE001
            logger.warning("Edge-TTS failed (%s); trying gTTS", exc)
            path.unlink(missing_ok=True)
        try:
            from gtts import gTTS

            gTTS(text=text, lang=gtts_lang or "en").save(str(path))
            return path
        except Exception as exc:  # noqa: BLE001
            path.unlink(missing_ok=True)
            raise ExternalServiceError("Speech generation failed. Check the internet connection.") from exc
