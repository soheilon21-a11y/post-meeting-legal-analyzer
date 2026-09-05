from __future__ import annotations

from typing import Any

import pytest

from app.application.exceptions.processing import ProcessingError
from app.infrastructure.embeddings.ollama_embeddings import OllamaEmbeddings


class FakeEmbedClient:
    """Deterministic fake Ollama client for embedding unit tests."""

    def __init__(self, embeddings: list[list[float]]) -> None:
        self._embeddings = embeddings
        self.calls: list[dict[str, Any]] = []

    def embed(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        return {"embeddings": self._embeddings}


class FailingEmbedClient:
    def embed(self, **kwargs: Any) -> dict[str, Any]:
        raise ConnectionError("connection refused")


@pytest.mark.anyio
async def test_embed_returns_vectors_in_order() -> None:
    adapter = OllamaEmbeddings(model_name="embed-model", base_url="http://test")
    adapter._client = FakeEmbedClient([[0.1, 0.2], [0.3, 0.4]])  # type: ignore[attr-defined]

    result = await adapter.embed(["first text", "second text"])

    assert result == ((0.1, 0.2), (0.3, 0.4))


@pytest.mark.anyio
async def test_embed_passes_model_and_batched_input_to_client() -> None:
    fake = FakeEmbedClient([[0.5], [0.6]])
    adapter = OllamaEmbeddings(model_name="embed-model", base_url="http://test")
    adapter._client = fake  # type: ignore[attr-defined]

    await adapter.embed(("alpha", "beta"))

    assert len(fake.calls) == 1
    assert fake.calls[0]["model"] == "embed-model"
    assert fake.calls[0]["input"] == ["alpha", "beta"]


@pytest.mark.anyio
async def test_embed_empty_input_returns_empty_tuple_without_client_call() -> None:
    fake = FakeEmbedClient([])
    adapter = OllamaEmbeddings(model_name="embed-model", base_url="http://test")
    adapter._client = fake  # type: ignore[attr-defined]

    result = await adapter.embed([])

    assert result == ()
    assert fake.calls == []


@pytest.mark.anyio
async def test_embed_raises_processing_error_on_client_failure() -> None:
    adapter = OllamaEmbeddings(model_name="embed-model", base_url="http://test")
    adapter._client = FailingEmbedClient()  # type: ignore[attr-defined]

    with pytest.raises(ProcessingError, match="embed call failed"):
        await adapter.embed(["text"])


@pytest.mark.anyio
async def test_embed_raises_processing_error_on_vector_count_mismatch() -> None:
    adapter = OllamaEmbeddings(model_name="embed-model", base_url="http://test")
    adapter._client = FakeEmbedClient([[0.1]])  # type: ignore[attr-defined]

    with pytest.raises(ProcessingError, match="unexpected number of embeddings"):
        await adapter.embed(["one", "two"])
