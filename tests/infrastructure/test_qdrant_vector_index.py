from __future__ import annotations

import pytest
from qdrant_client import QdrantClient

from app.application.dtos.internal.vector_index import IndexedChunk
from app.application.exceptions.processing import ProcessingError
from app.infrastructure.retrieval.qdrant_vector_index import QdrantVectorIndex
from app.infrastructure.retrieval.qdrant_vector_index import point_id_for_chunk


def _chunk(
    chunk_id: str,
    matter_id: str,
    text: str,
    vector: tuple[float, ...],
    source_id: str = "doc-1",
    position: int | None = None,
) -> IndexedChunk:
    return IndexedChunk(
        chunk_id=chunk_id,
        matter_id=matter_id,
        source_id=source_id,
        text=text,
        vector=vector,
        position=position,
    )


@pytest.fixture
def in_memory_client() -> QdrantClient:
    return QdrantClient(":memory:")


@pytest.mark.anyio
async def test_upsert_and_search_roundtrip(in_memory_client: QdrantClient) -> None:
    index = QdrantVectorIndex("legal_corpus", dimension=3, client=in_memory_client)

    await index.upsert(
        [
            _chunk("chunk-a", "matter-1", "The supplier is liable.", (1.0, 0.0, 0.0)),
            _chunk("chunk-b", "matter-1", "Termination requires notice.", (0.0, 1.0, 0.0)),
        ]
    )

    hits = await index.search((1.0, 0.0, 0.0), limit=5)

    assert len(hits) == 2
    assert hits[0].chunk_id == "chunk-a"
    assert hits[0].text == "The supplier is liable."
    assert hits[0].source_id == "doc-1"
    assert hits[0].score == pytest.approx(1.0)


@pytest.mark.anyio
async def test_search_filters_by_matter_id(in_memory_client: QdrantClient) -> None:
    index = QdrantVectorIndex("legal_corpus", dimension=3, client=in_memory_client)

    await index.upsert(
        [
            _chunk("chunk-a", "matter-1", "First matter text.", (1.0, 0.0, 0.0)),
            _chunk("chunk-b", "matter-2", "Second matter text.", (1.0, 0.0, 0.0)),
        ]
    )

    hits = await index.search((1.0, 0.0, 0.0), limit=5, matter_id="matter-2")

    assert len(hits) == 1
    assert hits[0].chunk_id == "chunk-b"


@pytest.mark.anyio
async def test_search_respects_score_threshold(in_memory_client: QdrantClient) -> None:
    index = QdrantVectorIndex("legal_corpus", dimension=3, client=in_memory_client)

    await index.upsert(
        [
            _chunk("chunk-a", "matter-1", "Matching text.", (1.0, 0.0, 0.0)),
            _chunk("chunk-b", "matter-1", "Orthogonal text.", (0.0, 1.0, 0.0)),
        ]
    )

    hits = await index.search((1.0, 0.0, 0.0), limit=5, score_threshold=0.5)

    assert [hit.chunk_id for hit in hits] == ["chunk-a"]


@pytest.mark.anyio
async def test_upsert_is_idempotent_for_same_chunk_id(in_memory_client: QdrantClient) -> None:
    index = QdrantVectorIndex("legal_corpus", dimension=3, client=in_memory_client)

    item = _chunk("chunk-a", "matter-1", "Original text.", (1.0, 0.0, 0.0))
    await index.upsert([item])
    await index.upsert([_chunk("chunk-a", "matter-1", "Updated text.", (1.0, 0.0, 0.0))])

    hits = await index.search((1.0, 0.0, 0.0), limit=5)

    assert len(hits) == 1
    assert hits[0].text == "Updated text."


@pytest.mark.anyio
async def test_search_on_missing_collection_returns_empty(in_memory_client: QdrantClient) -> None:
    index = QdrantVectorIndex("legal_corpus", dimension=3, client=in_memory_client)

    hits = await index.search((1.0, 0.0, 0.0), limit=5)

    assert hits == ()


@pytest.mark.anyio
async def test_dimension_mismatch_raises_processing_error(in_memory_client: QdrantClient) -> None:
    first = QdrantVectorIndex("legal_corpus", dimension=3, client=in_memory_client)
    await first.upsert([_chunk("chunk-a", "matter-1", "Text.", (1.0, 0.0, 0.0))])

    second = QdrantVectorIndex("legal_corpus", dimension=8, client=in_memory_client)

    with pytest.raises(ProcessingError, match="dimension"):
        await second.search((1.0, 0.0, 0.0), limit=5)


def test_point_id_is_deterministic() -> None:
    assert point_id_for_chunk("chunk-a") == point_id_for_chunk("chunk-a")
    assert point_id_for_chunk("chunk-a") != point_id_for_chunk("chunk-b")


@pytest.mark.anyio
async def test_scroll_by_matter_returns_all_points_for_that_matter(
    in_memory_client: QdrantClient,
) -> None:
    index = QdrantVectorIndex("legal_corpus", dimension=3, client=in_memory_client)

    await index.upsert(
        [
            _chunk("chunk-a", "matter-1", "First.", (1.0, 0.0, 0.0), position=0),
            _chunk("chunk-b", "matter-1", "Second.", (0.0, 1.0, 0.0), position=1),
            _chunk("chunk-c", "matter-2", "Other matter.", (0.0, 0.0, 1.0)),
        ]
    )

    hits = await index.scroll_by_matter("matter-1")

    assert sorted(hit.chunk_id for hit in hits) == ["chunk-a", "chunk-b"]
    by_id = {hit.chunk_id: hit for hit in hits}
    assert by_id["chunk-a"].position == 0
    assert by_id["chunk-b"].position == 1
    assert by_id["chunk-a"].source_id == "doc-1"


@pytest.mark.anyio
async def test_scroll_by_matter_on_missing_collection_returns_empty(
    in_memory_client: QdrantClient,
) -> None:
    index = QdrantVectorIndex("legal_corpus", dimension=3, client=in_memory_client)

    hits = await index.scroll_by_matter("matter-1")

    assert hits == ()
    assert not in_memory_client.collection_exists("legal_corpus")
