from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from app.application.dtos.internal.vector_index import IndexedChunk
from app.application.dtos.internal.vector_index import VectorHit
from app.application.exceptions.processing import ProcessingError
from app.infrastructure.retrieval.rag_retrieval import EmbeddedRetrieval

if TYPE_CHECKING:
    from collections.abc import Sequence


class FakeEmbeddings:
    def __init__(self, vectors: tuple[tuple[float, ...], ...] = ((0.1, 0.2),)) -> None:
        self._vectors = vectors
        self.seen_texts: list[str] = []

    async def embed(self, texts: Sequence[str]) -> tuple[tuple[float, ...], ...]:
        self.seen_texts.extend(texts)
        return self._vectors


class FailingEmbeddings:
    async def embed(self, texts: Sequence[str]) -> tuple[tuple[float, ...], ...]:
        raise ProcessingError("embedding_generation", "Ollama embed call failed")


class FakeIndex:
    def __init__(self, hits: tuple[VectorHit, ...] = ()) -> None:
        self._hits = hits
        self.search_calls: list[dict[str, object]] = []

    async def upsert(self, items: Sequence[IndexedChunk]) -> None:
        return None

    async def search(
        self,
        vector: Sequence[float],
        limit: int,
        *,
        matter_id: str | None = None,
        score_threshold: float | None = None,
    ) -> tuple[VectorHit, ...]:
        self.search_calls.append(
            {
                "vector": tuple(vector),
                "limit": limit,
                "matter_id": matter_id,
                "score_threshold": score_threshold,
            }
        )
        return self._hits


class FailingIndex:
    async def upsert(self, items: Sequence[IndexedChunk]) -> None:
        return None

    async def search(
        self,
        vector: Sequence[float],
        limit: int,
        *,
        matter_id: str | None = None,
        score_threshold: float | None = None,
    ) -> tuple[VectorHit, ...]:
        raise ProcessingError("vector_index_search", "Qdrant search failed")


@pytest.mark.anyio
async def test_retrieve_maps_hits_to_evidence_inputs() -> None:
    hits = (
        VectorHit(
            chunk_id="chunk-a",
            source_id="contract-1",
            text="The supplier shall indemnify the customer.",
            score=0.91,
            page_number=3,
            start_offset=10,
            end_offset=52,
        ),
    )
    retrieval = EmbeddedRetrieval(FakeEmbeddings(), FakeIndex(hits), score_threshold=0.65)

    evidence = await retrieval.retrieve("matter-1", "supplier liability", limit=20)

    assert len(evidence) == 1
    assert evidence[0].quote == "The supplier shall indemnify the customer."
    assert evidence[0].source_id == "contract-1"
    assert evidence[0].page_number == 3
    assert evidence[0].start_offset == 10
    assert evidence[0].end_offset == 52


@pytest.mark.anyio
async def test_retrieve_passes_scope_threshold_and_limit_to_index() -> None:
    index = FakeIndex()
    retrieval = EmbeddedRetrieval(FakeEmbeddings(), index, score_threshold=0.7)

    await retrieval.retrieve("matter-9", "query text", limit=5)

    assert index.search_calls == [
        {
            "vector": (0.1, 0.2),
            "limit": 5,
            "matter_id": "matter-9",
            "score_threshold": 0.7,
        }
    ]


@pytest.mark.anyio
async def test_retrieve_degrades_to_empty_when_embeddings_fail() -> None:
    retrieval = EmbeddedRetrieval(FailingEmbeddings(), FakeIndex())

    evidence = await retrieval.retrieve("matter-1", "query text", limit=20)

    assert evidence == ()


@pytest.mark.anyio
async def test_retrieve_degrades_to_empty_when_index_fails() -> None:
    retrieval = EmbeddedRetrieval(FakeEmbeddings(), FailingIndex())

    evidence = await retrieval.retrieve("matter-1", "query text", limit=20)

    assert evidence == ()
