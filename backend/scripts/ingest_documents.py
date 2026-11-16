"""Bulk-index every PDF/TXT/MD in knowledge_base/documents/ (alternative to uploading one by one).

    cd backend
    python -m scripts.ingest_documents            # index new files only
    python -m scripts.ingest_documents --reindex  # rebuild everything

The document title is the file name (underscores become spaces). Put the original
source URL in a sidecar file `<name>.url` next to the PDF to have it stored.
"""
import argparse
import shutil
import uuid
from pathlib import Path

from sqlalchemy import select

from app.core.config import PROJECT_ROOT, get_settings
from app.db.session import SessionLocal
from app.models import Document
from app.services.container import ServiceContainer
from app.services.rag.ingest import ingest_file

SOURCE_DIR = PROJECT_ROOT / "knowledge_base" / "documents"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reindex", action="store_true")
    args = parser.parse_args()
    settings = get_settings()
    settings.ensure_dirs()
    services = ServiceContainer(settings)
    files = sorted(p for p in SOURCE_DIR.glob("*") if p.suffix.lower() in {".pdf", ".txt", ".md"}
                   and p.stem.lower() not in {"readme", "sources"})  # folder notes, not farming documents
    if not files:
        print(f"No files found in {SOURCE_DIR}")
        return

    db = SessionLocal()
    try:
        for path in files:
            existing = db.scalars(select(Document).where(Document.original_filename == path.name)).first()
            if existing and existing.status == "indexed" and not args.reindex:
                print(f"skip     {path.name} (already indexed)")
                continue
            url_file = path.with_suffix(".url")
            if existing is None:
                stored = settings.document_dir / f"{uuid.uuid4().hex}{path.suffix.lower()}"
                shutil.copyfile(path, stored)
                existing = Document(
                    title=path.stem.replace("_", " ").strip(), original_filename=path.name,
                    stored_path=str(stored), file_size_bytes=path.stat().st_size, status="processing",
                    source_url=url_file.read_text(encoding="utf-8").strip() if url_file.exists() else None,
                )
                db.add(existing)
                db.commit()
            try:
                pages, chunks = ingest_file(
                    path=Path(existing.stored_path), document_id=existing.id, title=existing.title,
                    embedder=services.embedder, store=services.vector_store,
                    chunk_size=settings.CHUNK_SIZE, overlap=settings.CHUNK_OVERLAP,
                )
                existing.num_pages, existing.num_chunks, existing.status = pages, chunks, "indexed"
                existing.error_message = None
                print(f"indexed  {path.name}: {pages} pages, {chunks} chunks")
            except Exception as exc:  # noqa: BLE001
                existing.status, existing.error_message = "failed", str(exc)[:500]
                print(f"FAILED   {path.name}: {exc}")
            db.commit()
        print(f"Vector store now holds {services.vector_store.count()} chunks")
    finally:
        db.close()


if __name__ == "__main__":
    main()
