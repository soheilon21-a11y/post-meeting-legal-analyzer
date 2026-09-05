from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter
from pydantic import BaseModel
from pydantic import Field

from app.application.services.chunker import Chunker
from app.application.services.corpus_indexing import CorpusIndexingService
from app.core.config import get_settings
from app.infrastructure.ai.tokenizers import SimpleTokenizer
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


@router.post("/documents", response_model=IndexDocumentResponse)
async def index_document(request: IndexDocumentRequest) -> IndexDocumentResponse:
    """Chunk, locally embed, and index document text for RAG retrieval.

    The text is split with the structure-aware chunker, embedded with the
    local Ollama embedding model, and upserted into the vector index under
    the supplied matter scope.  Reindexing the same ``source_id`` with the
    same content is idempotent.
    """
    settings = get_settings()
    source_id = request.source_id or str(uuid4())

    chunker = Chunker(
        SimpleTokenizer(),
        max_tokens_per_chunk=settings.ai.chunk_size_tokens,
    )
    service = CorpusIndexingService(
        chunker=chunker,
        embeddings=OllamaEmbeddings(),
        index=QdrantVectorIndex.from_settings(),
    )

    chunks_indexed = await service.index_text(request.matter_id, source_id, request.text)

    return IndexDocumentResponse(
        source_id=source_id,
        matter_id=request.matter_id,
        chunks_indexed=chunks_indexed,
        embedding_model=settings.ollama.embedding_model,
    )
