"""Audio conversion with FFmpeg.

Browsers record WebM/Opus (Chrome) or MP4/AAC (Safari). Whisper works best on
16 kHz mono WAV, so every recording is converted before transcription.
FFmpeg must be installed and on PATH (see docs/SETUP_WINDOWS.md).
"""
import json
import shutil
import subprocess
from pathlib import Path

from app.core.exceptions import AppError, FileValidationError


def _require(binary: str) -> str:
    path = shutil.which(binary)
    if not path:
        raise AppError(
            f"{binary} is not installed or not on PATH. Install FFmpeg and restart the terminal.",
            code="ffmpeg_missing",
            status_code=500,
        )
    return path


def convert_to_wav16k(src: Path, dst: Path) -> Path:
    ffmpeg = _require("ffmpeg")
    cmd = [ffmpeg, "-y", "-loglevel", "error", "-i", str(src), "-ac", "1", "-ar", "16000", "-vn", str(dst)]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0 or not dst.exists():
        raise FileValidationError("Could not read the audio file. Please record again.")
    return dst


def audio_duration_seconds(path: Path) -> float:
    ffprobe = _require("ffprobe")
    cmd = [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    try:
        return float(json.loads(result.stdout)["format"]["duration"])
    except (KeyError, ValueError, json.JSONDecodeError) as exc:
        raise FileValidationError("Could not read the audio duration") from exc
