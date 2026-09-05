from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from typing import Any

from app.application.exceptions.processing import ProcessingError
from app.application.ports.embeddings import EmbeddingPort
from app.core.config import get_settings

if TYPE_CHECKING:
    from collections.abc import Sequence


class OllamaEmbeddings(EmbeddingPort):
    """Concrete EmbeddingPort adapter using a local Ollama server.

    Embeddings are generated in a single batched call so that only one
    request is made per indexing or retrieval operation.  The blocking
    client call runs in a worker thread to keep the event loop responsive.
    """

    def __init__(
        self,
        model_name: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self._model_name = model_name or get_settings().ollama.embedding_model
        self._base_url = base_url or get_settings().ollama.base_url
        self._timeout = get_settings().ollama.timeout_seconds
        self._client: Any | None = None

    async def embed(self, texts: Sequence[str]) -> tuple[tuple[float, ...], ...]:
        if not texts:
            return ()

        try:
            import ollama
        except ImportError as exc:
            raise ProcessingError(
                "embedding_generation", "ollama package is not installed"
            ) from exc

        client = self._client or ollama.Client(host=self._base_url, timeout=self._timeout)

        try:
            response = await asyncio.to_thread(
                client.embed,
                model=self._model_name,
                input=list(texts),
            )
        except Exception as exc:
            raise ProcessingError(
                "embedding_generation",
                f"Ollama embed call failed: {exc}",
            ) from exc

        if isinstance(response, dict):
            embeddings = response.get("embeddings")
        else:
            embeddings = getattr(response, "embeddings", None)

        if not embeddings or len(embeddings) != len(texts):
            raise ProcessingError(
                "embedding_generation",
                "Ollama returned an unexpected number of embeddings",
            )

        return tuple(tuple(float(value) for value in vector) for vector in embeddings)
