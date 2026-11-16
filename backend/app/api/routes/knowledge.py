"""Knowledge-base documents (admin upload/delete) and passage search (all users)."""
import logging
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.api.deps import get_current_user, get_services, require_admin
from app.core.config import get_settings
from app.core.exceptions import NotFoundError
from app.db.session import SessionLocal, get_db
from app.models import Document, User
from app.schemas.assistant import KnowledgeSearchRequest, KnowledgeSearchResponse
from app.schemas.auth import MessageResponse
from app.schemas.other import DocumentOut
from app.services.assistant import AssistantService
from app.services.container import ServiceContainer
from app.services.language_service import get_language
from app.services.rag.ingest import ingest_file
from app.utils.files import read_validated_upload, save_bytes

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/knowledge", tags=["Knowledge Base"])
settings = get_settings()


def index_document(document_id: int, services: ServiceContainer) -> None:
    """Runs after the upload response is sent. Uses its own DB session."""
    db = SessionLocal()
    try:
        doc = db.get(Document, document_id)
        if doc is None:
            return
        try:
            pages, chunks = ingest_file(
                path=Path(doc.stored_path), document_id=doc.id, title=doc.title,
                embedder=services.embedder, store=services.vector_store,
                chunk_size=settings.CHUNK_SIZE, overlap=settings.CHUNK_OVERLAP,
            )
            doc.num_pages, doc.num_chunks, doc.status, doc.error_message = pages, chunks, "indexed", None
        except Exception as exc:  # noqa: BLE001
            logger.exception("Indexing document %s failed", document_id)
            doc.status, doc.error_message = "failed", str(exc)[:500]
        db.commit()
    finally:
        db.close()


@router.post("/upload", response_model=DocumentOut, status_code=status.HTTP_202_ACCEPTED)
async def upload(
    background: BackgroundTasks,
    file: UploadFile = File(..., description="PDF, TXT or MD file"),
    title: str = Form(..., min_length=3, max_length=255),
    source_url: str | None = Form(None, max_length=500),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
    services: ServiceContainer = Depends(get_services),
):
    """Upload a document. Indexing runs in the background; poll GET /documents for status."""
    data, ext = await read_validated_upload(file, kind="document", max_mb=settings.MAX_PDF_MB)
    path = save_bytes(data, settings.document_dir, ext)
    doc = Document(
        title=title.strip(), original_filename=Path(file.filename or "document").name[:255],
        stored_path=str(path), source_url=source_url, file_size_bytes=len(data),
        status="processing", uploaded_by=admin.id,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    background.add_task(index_document, doc.id, services)
    return doc


@router.get("/documents", response_model=list[DocumentOut])
def list_documents(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return list(db.scalars(select(Document).order_by(Document.created_at.desc())))


@router.delete("/documents/{document_id}", response_model=MessageResponse)
def delete_document(
    document_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
    services: ServiceContainer = Depends(get_services),
):
    doc = db.get(Document, document_id)
    if doc is None:
        raise NotFoundError("Document not found")
    services.vector_store.delete_document(doc.id)
    Path(doc.stored_path).unlink(missing_ok=True)
    db.delete(doc)
    db.commit()
    return MessageResponse(message=f"Deleted '{doc.title}' and its search index")


@router.post("/search", response_model=KnowledgeSearchResponse)
async def search(
    body: KnowledgeSearchRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    services: ServiceContainer = Depends(get_services),
):
    """Find the most relevant passages (no AI answer). Shows exactly what the assistant would read."""
    lang = get_language(db, body.language_code) if body.language_code else user.preferred_language
    assistant = AssistantService(services, settings)
    english = await assistant.translate(body.query, lang.nllb_code, "eng_Latn")
    chunks = await run_in_threadpool(services.retriever.retrieve, english, body.top_n)
    return {
        "query_english": english,
        "results": [
            {"index": i, "title": c.title, "page": c.page, "document_id": c.document_id,
             "score": round(c.score, 4), "snippet": c.text, "kind": "document"}
            for i, c in enumerate(chunks, start=1)
        ],
    }
