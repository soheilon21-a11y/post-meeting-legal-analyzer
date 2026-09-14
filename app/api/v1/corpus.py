from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from typing import Annotated
from uuid import UUID
from uuid import uuid4

from fastapi import APIRouter
from fastapi import Depends
from fastapi import File
from fastapi import Form
from fastapi import Path as PathParam
from fastapi import Query
from fastapi import UploadFile
from pydantic import BaseModel
from pydantic import Field
from sqlalchemy import select

from app.api.dependencies.db import get_db
from app.application.services.chunker import Chunker
from app.application.services.corpus_indexing import CorpusIndexingService
from app.core.config import get_settings
from app.core.exceptions.domain import FileTooLargeError
from app.core.exceptions.domain import NotFoundError
from app.db.models.document import DocumentSegment
from app.db.models.matter import Matter
from app.infrastructure.ai.tokenizers import SimpleTokenizer
from app.infrastructure.documents.extraction import MAX_UPLOAD_BYTES
from app.infrastructure.documents.extraction import extract_text
from app.infrastructure.embeddings import OllamaEmbeddings
from app.infrastructure.retrieval import QdrantVectorIndex

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.application.dtos.internal.vector_index import VectorHit

router = APIRouter(prefix="/corpus", tags=["Corpus"])


class IndexDocumentRequest(BaseModel):
    matter_id: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1)
    source_id: str | None = Field(default=None, max_length=200)


class IndexDocumentResponse(BaseModel):
    source_id: str
    matter_id: str
    chunks_indexed: int
    embedding_model: str


async def _index_extracted_text(matter_id: str, source_id: str, text: str) -> IndexDocumentResponse:
    """Run the shared indexing pipeline: structure-aware chunking →
    nomic-embed-text embeddings → Qdrant upsert.

    The stored chunk payloads carry the (already trimmed) ``source_id``, so
    the indexed text stays retrievable through
    ``GET /corpus/documents/{source_id}/text``."""
    settings = get_settings()

    chunker = Chunker(
        SimpleTokenizer(),
        max_tokens_per_chunk=settings.ai.chunk_size_tokens,
    )
    service = CorpusIndexingService(
        chunker=chunker,
        embeddings=OllamaEmbeddings(),
        index=QdrantVectorIndex.from_settings(),
    )

    chunks_indexed = await service.index_text(matter_id, source_id, text)

    return IndexDocumentResponse(
        source_id=source_id,
        matter_id=matter_id,
        chunks_indexed=chunks_indexed,
        embedding_model=settings.ollama.embedding_model,
    )


@router.post("/documents", response_model=IndexDocumentResponse)
async def index_document(request: IndexDocumentRequest) -> IndexDocumentResponse:
    """Chunk, locally embed, and index document text for RAG retrieval.

    The text is split with the structure-aware chunker, embedded with the
    local Ollama embedding model, and upserted into the vector index under
    the supplied matter scope.  Reindexing the same ``source_id`` with the
    same content is idempotent.  Surrounding whitespace on ``source_id`` is
    stripped before use, so the document stays findable afterwards via
    ``GET /corpus/documents/{source_id}/text``.
    """
    source_id = (request.source_id or "").strip() or str(uuid4())
    return await _index_extracted_text(
        request.matter_id.strip(),
        source_id,
        request.text,
    )


@router.post("/documents/upload", response_model=IndexDocumentResponse)
async def upload_document(
    file: Annotated[UploadFile, File(description="Document file: PDF, DOCX, TXT or Markdown")],
    matter_id: Annotated[str, Form(min_length=1, max_length=200)],
    source_id: Annotated[str | None, Form(max_length=200)] = None,
) -> IndexDocumentResponse:
    """Upload a meeting transcript or contract file and index it for RAG.

    Accepts ``multipart/form-data`` with a ``file`` part plus a ``matter_id``
    form field and an optional ``source_id`` (defaults to the file name
    without its extension).  Surrounding whitespace on both form fields is
    stripped before use, so stray spaces in HTML form values cannot create
    unfindable documents.

    Supported formats: PDF (.pdf), DOCX (.docx), TXT (.txt), Markdown (.md);
    anything else is rejected with 422.  Files up to 20 MB are accepted
    (larger files return 413).  Text is extracted from PDF pages and DOCX
    paragraphs, then indexed through the same structure-aware chunking,
    local embedding and vector-upsert pipeline as `POST /corpus/documents`.
    Scanned/image-only documents with no extractable text are rejected
    with 422.
    """
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise FileTooLargeError(
            size_bytes=len(data),
            max_bytes=MAX_UPLOAD_BYTES,
            filename=file.filename,
        )

    filename = Path((file.filename or "").replace("\\", "/")).name
    text = extract_text(filename, data)

    resolved_source_id = (source_id or "").strip() or Path(filename).stem or str(uuid4())
    return await _index_extracted_text(matter_id.strip(), resolved_source_id, text)


class CorpusDocumentTextResponse(BaseModel):
    matter_id: str
    source_id: str
    document_id: str | None
    document_version_id: str | None
    title: str
    segment_count: int
    text: str


async def _resolve_matter_by_handle(session: AsyncSession, raw: str) -> Matter:
    """Look up a Matter by UUID or matter_number (same handles as everywhere)."""
    try:
        matter_id = UUID(raw)
    except ValueError:
        result = await session.execute(select(Matter).where(Matter.matter_number == raw))
        matter = result.scalars().first()
        if matter is None:
            raise NotFoundError(entity="Matter", identifier=raw) from None
        return matter
    matter = await session.get(Matter, matter_id)
    if matter is None:
        raise NotFoundError(entity="Matter", identifier=raw)
    return matter


_UNPOSITIONED = 2**31


def _matter_handles(matter: Matter, raw_matter_id: str) -> list[str]:
    """All strings the matter may have been indexed in the corpus under."""
    candidates = [
        raw_matter_id.strip(),
        str(matter.id),
        getattr(matter, "matter_number", None) or "",
    ]
    handles: list[str] = []
    for candidate in candidates:
        if candidate and candidate not in handles:
            handles.append(candidate)
    return handles


async def _corpus_index_texts(
    matter: Matter,
    raw_matter_id: str,
    source_id: str,
) -> tuple[str, ...]:
    """Return the indexed chunk texts of a corpus document by source_id.

    Matches the (whitespace-stripped) ``source_id`` recorded in the vector
    index payloads of documents indexed through ``POST /corpus/documents``
    and ``POST /corpus/documents/upload``, in original chunk order.  This is
    a metadata scroll — it never calls the embedding model.
    """
    index = QdrantVectorIndex.from_settings()
    matching: list[VectorHit] = []
    for handle in _matter_handles(matter, raw_matter_id):
        hits = await index.scroll_by_matter(handle)
        matching = [hit for hit in hits if hit.source_id.strip() == source_id and hit.text.strip()]
        if matching:
            break
    matching.sort(
        key=lambda hit: (
            hit.page_number or 0,
            hit.position if hit.position is not None else _UNPOSITIONED,
            hit.chunk_id,
        )
    )
    return tuple(hit.text for hit in matching)


@router.get(
    "/documents/{source_id}/text",
    response_model=CorpusDocumentTextResponse,
    summary="Download the extracted text of a stored corpus document",
)
async def get_document_text(
    source_id: Annotated[str, PathParam(min_length=1, max_length=200)],
    matter_id: Annotated[
        str,
        Query(min_length=1, max_length=200, description="Matter UUID or matter_number"),
    ],
    session: AsyncSession = Depends(get_db),
) -> CorpusDocumentTextResponse:
    """Return the stored text of any document indexed into this matter's
    corpus, addressed by its ``source_id``.

    Surrounding whitespace is stripped from ``source_id`` before lookup.  Two
    sources are resolved, in order:

    1. Documents persisted as PostgreSQL rows (redline uploads): matched on
       the file name stem recorded in ``Document.source_filename`` or on
       ``Document.title`` (latest version, segments joined in reading order).
    2. Corpus-indexed documents (``POST /corpus/documents`` JSON-direct or
       ``POST /corpus/documents/upload``), whose text lives in the vector
       index: matched on the stored chunk payload ``source_id`` (also
       whitespace-stripped on both sides).

    Unknown matters/documents return 404.  The resolution never calls the
    embedding model — the vector-index path is a payload metadata scroll.
    """
    resolved_source_id = source_id.strip()
    matter = await _resolve_matter_by_handle(session, matter_id)

    document = next(
        (
            doc
            for doc in (matter.documents or ())
            if getattr(doc, "deleted_at", None) is None
            and (
                Path(doc.source_filename).stem.strip() == resolved_source_id
                or doc.title.strip() == resolved_source_id
            )
        ),
        None,
    )
    versions = list(getattr(document, "versions", None) or ()) if document else []
    if document is not None and versions:
        version = versions[-1]

        result = await session.execute(
            select(DocumentSegment.text)
            .where(DocumentSegment.document_version_id == version.id)
            .order_by(DocumentSegment.page_number, DocumentSegment.paragraph_number)
        )
        texts = [text for text in result.scalars().all() if text and text.strip()]
        if texts:
            return CorpusDocumentTextResponse(
                matter_id=str(matter.id),
                source_id=resolved_source_id,
                document_id=str(document.id),
                document_version_id=str(version.id),
                title=document.title,
                segment_count=len(texts),
                text="\n\n".join(texts),
            )

    corpus_texts = await _corpus_index_texts(matter, matter_id, resolved_source_id)
    if not corpus_texts:
        raise NotFoundError(entity="Document", identifier=resolved_source_id)

    return CorpusDocumentTextResponse(
        matter_id=str(matter.id),
        source_id=resolved_source_id,
        document_id=None,
        document_version_id=None,
        title=resolved_source_id,
        segment_count=len(corpus_texts),
        text="\n\n".join(corpus_texts),
    )
