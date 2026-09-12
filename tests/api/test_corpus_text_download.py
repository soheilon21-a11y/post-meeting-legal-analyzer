from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from uuid import UUID
from uuid import uuid4

import pytest
from httpx import ASGITransport
from httpx import AsyncClient

from app.api.dependencies.db import get_db
from app.api.v1 import corpus as corpus_api
from app.main import create_app

MATTER_ID = UUID("77777777-7777-7777-7777-777777777777")
DOCUMENT_ID = uuid4()
VERSION_ID = uuid4()

SEGMENT_TEXTS = [
    "Payment is due within 30 days of invoice receipt.",
    "Supplier liability is capped at direct damages.",
]


def _text_result(texts: list[str]) -> MagicMock:
    result = MagicMock()
    result.scalars.return_value.all.return_value = texts
    return result


def _matter_result(matter: object | None) -> MagicMock:
    result = MagicMock()
    result.scalars.return_value.first.return_value = matter
    return result


def _matter() -> SimpleNamespace:
    version = SimpleNamespace(id=VERSION_ID)
    document = SimpleNamespace(
        id=DOCUMENT_ID,
        title="Supplier Agreement v1",
        source_filename="supplier_v1.pdf",
        deleted_at=None,
        versions=[version],
    )
    return SimpleNamespace(id=MATTER_ID, documents=[document])


def _client(session: AsyncMock) -> AsyncClient:
    app = create_app()
    app.dependency_overrides[get_db] = lambda: session
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.anyio
async def test_document_text_returns_segments_in_order() -> None:
    session = AsyncMock()
    session.execute = AsyncMock(
        side_effect=[_matter_result(_matter()), _text_result(SEGMENT_TEXTS)]
    )

    async with _client(session) as client:
        response = await client.get(
            "/api/v1/corpus/documents/supplier_v1/text", params={"matter_id": "matter-1"}
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert UUID(body["matter_id"]) == MATTER_ID
    assert body["source_id"] == "supplier_v1"
    assert UUID(body["document_id"]) == DOCUMENT_ID
    assert UUID(body["document_version_id"]) == VERSION_ID
    assert body["title"] == "Supplier Agreement v1"
    assert body["segment_count"] == 2
    assert body["text"] == "\n\n".join(SEGMENT_TEXTS)


@pytest.mark.anyio
async def test_document_text_matches_by_title_and_works_with_matter_uuid() -> None:
    matter = _matter()
    session = AsyncMock()
    session.get = AsyncMock(return_value=matter)
    session.execute = AsyncMock(side_effect=[_text_result(SEGMENT_TEXTS)])

    async with _client(session) as client:
        by_title = await client.get(
            "/api/v1/corpus/documents/Supplier%20Agreement%20v1/text",
            params={"matter_id": str(MATTER_ID)},
        )

    assert by_title.status_code == 200, by_title.text
    assert by_title.json()["source_id"] == "Supplier Agreement v1"
    # Matter lookups by UUID go through session.get; only the segment query
    # hits execute.
    assert session.get.await_args.args[0] is not None
    assert session.execute.await_count == 1


@pytest.mark.anyio
async def test_document_text_unknown_source_returns_404() -> None:
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[_matter_result(_matter())])

    async with _client(session) as client:
        response = await client.get(
            "/api/v1/corpus/documents/ghost_doc/text", params={"matter_id": "matter-1"}
        )

    assert response.status_code == 404, response.text
    assert "ghost_doc" in response.json()["detail"]
    assert session.execute.await_count == 1  # stopped before touching segments


@pytest.mark.anyio
async def test_document_text_unknown_matter_returns_404() -> None:
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[_matter_result(None)])

    async with _client(session) as client:
        response = await client.get(
            "/api/v1/corpus/documents/supplier_v1/text", params={"matter_id": "matter-nope"}
        )

    assert response.status_code == 404, response.text
    assert "matter-nope" in response.json()["detail"]


@pytest.mark.anyio
async def test_document_text_is_pure_local_read_never_touches_ai_pipeline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Guard: the text download must not call Ollama embeddings or Qdrant."""

    def _boom(*args: object, **kwargs: object) -> None:
        raise AssertionError("AI pipeline must not be invoked by corpus text download")

    monkeypatch.setattr(corpus_api, "OllamaEmbeddings", _boom)
    monkeypatch.setattr(corpus_api, "QdrantVectorIndex", _boom)

    session = AsyncMock()
    session.execute = AsyncMock(
        side_effect=[_matter_result(_matter()), _text_result(SEGMENT_TEXTS)]
    )

    async with _client(session) as client:
        response = await client.get(
            "/api/v1/corpus/documents/supplier_v1/text", params={"matter_id": "matter-1"}
        )

    assert response.status_code == 200, response.text
