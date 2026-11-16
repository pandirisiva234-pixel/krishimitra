"""Safe handling of uploaded files.

Checks done before anything is saved:
1. size limit,
2. extension whitelist,
3. "magic bytes" (the first bytes of the file) so a renamed .exe cannot pass as .jpg.
Files are saved under a random name, so user-supplied names never reach the filesystem.
"""
import uuid
from pathlib import Path

from fastapi import UploadFile

from app.core.exceptions import FileValidationError

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
AUDIO_EXTS = {".webm", ".wav", ".mp3", ".ogg", ".m4a", ".mp4", ".oga"}
DOCUMENT_EXTS = {".pdf", ".txt", ".md"}


def _looks_like(kind: str, head: bytes) -> bool:
    if kind == "image":
        return (
            head.startswith(b"\xff\xd8\xff")  # JPEG
            or head.startswith(b"\x89PNG\r\n\x1a\n")  # PNG
            or (head[:4] == b"RIFF" and head[8:12] == b"WEBP")  # WebP
        )
    if kind == "audio":
        return (
            head.startswith(b"\x1a\x45\xdf\xa3")  # WebM / Matroska
            or (head[:4] == b"RIFF" and head[8:12] == b"WAVE")  # WAV
            or head.startswith(b"ID3")  # MP3 with tags
            or head[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2")  # MP3 frame
            or head.startswith(b"OggS")  # OGG / Opus
            or head[4:8] == b"ftyp"  # M4A / MP4 (iPhone recordings)
        )
    if kind == "document":
        return head.startswith(b"%PDF")
    return False


async def read_validated_upload(upload: UploadFile, *, kind: str, max_mb: int) -> tuple[bytes, str]:
    """Read the upload into memory after validating it. Returns (data, extension)."""
    allowed = {"image": IMAGE_EXTS, "audio": AUDIO_EXTS, "document": DOCUMENT_EXTS}[kind]
    ext = Path(upload.filename or "").suffix.lower()
    if ext not in allowed:
        raise FileValidationError(f"Unsupported file type '{ext or 'none'}'. Allowed: {', '.join(sorted(allowed))}")

    max_bytes = max_mb * 1024 * 1024
    data = await upload.read(max_bytes + 1)
    if len(data) == 0:
        raise FileValidationError("The uploaded file is empty")
    if len(data) > max_bytes:
        raise FileValidationError(f"File is too large. Maximum size is {max_mb} MB")

    # Plain-text knowledge files have no magic bytes; check they decode as text instead
    if kind == "document" and ext in {".txt", ".md"}:
        try:
            data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise FileValidationError("Text files must be UTF-8 encoded") from exc
    elif not _looks_like(kind, data[:16]):
        raise FileValidationError("File content does not match its extension")
    return data, ext


def save_bytes(data: bytes, directory: Path, ext: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = (directory / f"{uuid.uuid4().hex}{ext}").resolve()  # full, normalised path
    path.write_bytes(data)
    return path


def safe_child(directory: Path, filename: str) -> Path:
    """Resolve `filename` inside `directory`, rejecting path traversal like '../../.env'."""
    candidate = (directory / filename).resolve()
    if candidate.parent != directory.resolve() or not candidate.is_file():
        raise FileValidationError("File not found", code="not_found", status_code=404)
    return candidate