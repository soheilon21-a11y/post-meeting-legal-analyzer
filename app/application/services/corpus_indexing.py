from __future__ import annotations

import hashlib
import uuid
from typing import TYPE_CHECKING

from app.application.dtos.internal.vector_index import IndexedChunk
from app.application.exceptions.validation import ApplicationValidationError
from app.domain.document.entities import DocumentSegment
from app.domain.document.value_objects import ContentHash

if TYPE_CHECKING:
    from app.application.ports.embeddings import EmbeddingPort
    from app.application.ports.vector_index import VectorIndexPort
    from app.application.services.chunker import Chunker

_CHUNK_ID_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "post-meeting-legal-analyzer.chunks")


class CorpusIndexingService:
    """Chunks document text, embeds the chunks locally, and upserts them.

    Reuses the structure-aware ``Chunker`` by mapping plain text paragraphs
    onto ``DocumentSegment`` entities before chunking.
    """

    def __init__(
        self,
        chunker: Chunker,
        embeddings: EmbeddingPort,
        index: VectorIndexPort,
    ) -> None:
        self._chunker = chunker
        self._embeddings = embeddings
        self._index = index

    async def index_text(self, matter_id: str, source_id: str, text: str) -> int:
        if not matter_id.strip():
            raise ApplicationValidationError("matter_id must not be blank", field="matter_id")
        if not source_id.strip():
            raise ApplicationValidationError("source_id must not be blank", field="source_id")
        if not text.strip():
            raise ApplicationValidationError("text must not be blank", field="text")

        segments = self._segments(text)
        chunks = await self._chunker.chunk_document(segments, source_id)
        if not chunks:
            return 0

        vectors = await self._embeddings.embed(tuple(chunk.text for chunk in chunks))
        items = tuple(
            IndexedChunk(
                chunk_id=self._chunk_id(source_id, position, chunk.text),
                matter_id=matter_id,
                source_id=source_id,
                text=chunk.text,
                vector=vector,
                page_number=chunk.metadata.page_number,
            )
            for position, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True))
        )
        await self._index.upsert(items)
        return len(items)

    @staticmethod
    def _segments(text: str) -> list[DocumentSegment]:
        paragraphs = [paragraph.strip() for paragraph in text.split("\n\n")]
        paragraphs = [paragraph for paragraph in paragraphs if paragraph]
        segments: list[DocumentSegment] = []
        for position, paragraph in enumerate(paragraphs, start=1):
            digest = hashlib.sha256(paragraph.encode("utf-8")).hexdigest()
            segments.append(
                DocumentSegment(
                    text=paragraph,
                    content_hash=ContentHash(digest),
                    paragraph_number=position,
                )
            )
        return segments

    @staticmethod
    def _chunk_id(source_id: str, position: int, text: str) -> str:
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        return str(uuid.uuid5(_CHUNK_ID_NAMESPACE, f"{source_id}:{position}:{digest}"))
