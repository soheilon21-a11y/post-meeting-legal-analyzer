from __future__ import annotations

from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter
from fastapi import File
from fastapi import Form
from fastapi import UploadFile
from pydantic import BaseModel
from pydantic import Field

from app.application.services.chunker import Chunker
from app.application.services.corpus_indexing import CorpusIndexingService
from app.core.config import get_settings
from app.core.exceptions.domain import FileTooLargeError
from app.infrastructure.ai.tokenizers import SimpleTokenizer
from app.infrastructure.documents.extraction import MAX_UPLOAD_BYTES
from app.infrastructure.documents.extraction import extract_text
from app.infrastructure.embeddings import OllamaEmbeddings
from app.infrastructure.retrieval import QdrantVectorIndex

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
