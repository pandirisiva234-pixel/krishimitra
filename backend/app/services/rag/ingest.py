"""Knowledge ingestion: file -> pages -> clean text -> chunks -> embeddings -> ChromaDB.

Chunks keep their page number so every answer can cite "Title, p. 12".
LangChain is used only for its well-tested text splitter.
"""
import logging
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class Chunk:
    text: str
    page: int | None
    index: int


def extract_pages(path: Path) -> list[tuple[int | None, str]]:
    """Return [(page_number, text)]. Text files count as a single page (None)."""
    if path.suffix.lower() == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        if reader.is_encrypted:
            try:
                reader.decrypt("")
            except Exception as exc:  # noqa: BLE001
                raise ValueError("PDF is password-protected") from exc
        pages = []
        for number, page in enumerate(reader.pages, start=1):
            try:
                pages.append((number, page.extract_text() or ""))
            except Exception:  # noqa: BLE001 - one bad page should not stop the document
                logger.warning("Could not read page %s of %s", number, path.name)
        return pages
    return [(None, path.read_text(encoding="utf-8"))]


def clean_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)  # join words hyphenated across lines
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)  # keep paragraph breaks
    text = re.sub(r"(?<!\n)\n(?!\n)", " ", text)  # single newlines inside a paragraph -> space
    text = re.sub(r"^\s*(page\s*)?\d+\s*$", "", text, flags=re.IGNORECASE | re.MULTILINE)  # lone page numbers
    return text.strip()


def chunk_pages(pages: list[tuple[int | None, str]], chunk_size: int, overlap: int) -> list[Chunk]:
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size, chunk_overlap=overlap, separators=["\n\n", "\n", ". ", " ", ""]
    )
    chunks: list[Chunk] = []
    for page, raw in pages:
        cleaned = clean_text(raw)
        if len(cleaned) < 40:  # skip blank / cover pages
            continue
        for piece in splitter.split_text(cleaned):
            if len(piece.strip()) >= 40:
                chunks.append(Chunk(piece.strip(), page, len(chunks)))
    return chunks


def ingest_file(
    *, path: Path, document_id: int, title: str, embedder, store, chunk_size: int, overlap: int
) -> tuple[int, int]:
    """Index one file. Returns (num_pages, num_chunks). Raises ValueError if nothing is readable."""
    pages = extract_pages(path)
    chunks = chunk_pages(pages, chunk_size, overlap)
    if not chunks:
        raise ValueError("No readable text found. Scanned PDFs need OCR before upload.")
    embeddings = embedder.encode([c.text for c in chunks])
    store.delete_document(document_id)  # makes re-indexing safe
    store.add(
        ids=[f"doc{document_id}-c{c.index}" for c in chunks],
        embeddings=embeddings,
        texts=[c.text for c in chunks],
        metadatas=[
            {"document_id": document_id, "title": title, "page": c.page if c.page is not None else -1,
             "chunk_index": c.index}
            for c in chunks
        ],
    )
    logger.info("Indexed '%s': %s pages, %s chunks", title, len(pages), len(chunks))
    return len(pages), len(chunks)
