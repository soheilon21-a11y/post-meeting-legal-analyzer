from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from app.application.exceptions.validation import ApplicationValidationError
from app.application.services.chunker import Chunker
from app.application.services.corpus_indexing import CorpusIndexingService
from app.infrastructure.ai.tokenizers import SimpleTokenizer

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.application.dtos.internal.vector_index import IndexedChunk
    from app.application.dtos.internal.vector_index import VectorHit


class FakeEmbeddings:
    def __init__(self) -> None:
        self.seen_texts: list[str] = []

    async def embed(self, texts: Sequence[str]) -> tuple[tuple[float, ...], ...]:
        self.seen_texts.extend(texts)
        return tuple((0.1 * (position + 1),) for position in range(len(texts)))


class FakeIndex:
    def __init__(self) -> None:
        self.upserted: list[IndexedChunk] = []

    async def upsert(self, items: Sequence[IndexedChunk]) -> None:
        self.upserted.extend(items)

    async def search(
        self,
        vector: Sequence[float],
        limit: int,
        *,
        matter_id: str | None = None,
        score_threshold: float | None = None,
    ) -> tuple[VectorHit, ...]:
        return ()


def _service() -> tuple[CorpusIndexingService, FakeEmbeddings, FakeIndex]:
    embeddings = FakeEmbeddings()
    index = FakeIndex()
    chunker = Chunker(SimpleTokenizer(), max_tokens_per_chunk=64)
    return CorpusIndexingService(chunker, embeddings, index), embeddings, index


@pytest.mark.anyio
async def test_index_text_chunks_embeds_and_upserts() -> None:
    service, embeddings, index = _service()
    text = (
        "The supplier shall be liable for all direct damages. "
        "Indirect damages are excluded unless gross negligence is proven.\n\n"
        "The customer may terminate the agreement for material breach."
    )

    count = await service.index_text("matter-1", "contract-1", text)

    assert count == 2
    assert len(embeddings.seen_texts) == 2
    assert len(index.upserted) == 2
    assert all(item.matter_id == "matter-1" for item in index.upserted)
    assert all(item.source_id == "contract-1" for item in index.upserted)
    assert index.upserted[0].vector != index.upserted[1].vector


@pytest.mark.anyio
async def test_index_text_chunk_ids_are_deterministic() -> None:
    service, _, first_index = _service()
    text = "The parties agree to arbitration."

    await service.index_text("matter-1", "doc-1", text)

    second_service, _, second_index = _service()
    await second_service.index_text("matter-1", "doc-1", text)

    assert [item.chunk_id for item in first_index.upserted] == [
        item.chunk_id for item in second_index.upserted
    ]


@pytest.mark.anyio
async def test_index_text_rejects_blank_inputs() -> None:
    service, _, _ = _service()

    with pytest.raises(ApplicationValidationError, match="matter_id"):
        await service.index_text("  ", "doc-1", "Some text.")
    with pytest.raises(ApplicationValidationError, match="source_id"):
        await service.index_text("matter-1", "", "Some text.")
    with pytest.raises(ApplicationValidationError, match="text"):
        await service.index_text("matter-1", "doc-1", "   ")
