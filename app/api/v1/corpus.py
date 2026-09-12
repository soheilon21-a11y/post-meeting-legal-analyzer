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
    nomic-embed-text embeddings → Qdrant upsert."""
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
    same content is idempotent.
    """
    source_id = request.source_id or str(uuid4())
    return await _index_extracted_text(request.matter_id, source_id, request.text)


@router.post("/documents/upload", response_model=IndexDocumentResponse)
async def upload_document(
    file: Annotated[UploadFile, File(description="Document file: PDF, DOCX, TXT or Markdown")],
    matter_id: Annotated[str, Form(min_length=1, max_length=200)],
    source_id: Annotated[str | None, Form(max_length=200)] = None,
) -> IndexDocumentResponse:
    """Upload a meeting transcript or contract file and index it for RAG.

    Accepts ``multipart/form-data`` with a ``file`` part plus a ``matter_id``
    form field and an optional ``source_id`` (defaults to the file name
    without its extension).

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

    resolved_source_id = source_id or Path(filename).stem or str(uuid4())
    return await _index_extracted_text(matter_id, resolved_source_id, text)


class CorpusDocumentTextResponse(BaseModel):
    matter_id: str
    source_id: str
    document_id: str
    document_version_id: str
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
    """Return the stored extracted text of a document, joined from its
    ``DocumentSegment`` rows in reading order (page, then paragraph).

    ``source_id`` matches the file name stem recorded when a redline upload
    persisted the document (``Document.source_filename``), or its title.  The
    latest document version is used.  Unknown matters/documents (or versions
    without any extracted text) return 404.  This is a local read of rows
    already in PostgreSQL — it never calls Ollama or the vector index.
    """
    matter = await _resolve_matter_by_handle(session, matter_id)

    document = next(
        (
            doc
            for doc in (matter.documents or ())
            if getattr(doc, "deleted_at", None) is None
            and (Path(doc.source_filename).stem == source_id or doc.title == source_id)
        ),
        None,
    )
    versions = list(getattr(document, "versions", None) or ()) if document else []
    if document is None or not versions:
        raise NotFoundError(entity="Document", identifier=source_id)
    version = versions[-1]

    result = await session.execute(
        select(DocumentSegment.text)
        .where(DocumentSegment.document_version_id == version.id)
        .order_by(DocumentSegment.page_number, DocumentSegment.paragraph_number)
    )
    texts = [text for text in result.scalars().all() if text and text.strip()]
    if not texts:
        raise NotFoundError(entity="Document", identifier=source_id)

    return CorpusDocumentTextResponse(
        matter_id=str(matter.id),
        source_id=source_id,
        document_id=str(document.id),
        document_version_id=str(version.id),
        title=document.title,
        segment_count=len(texts),
        text="\n\n".join(texts),
    )
