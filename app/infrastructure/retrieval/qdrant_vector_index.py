from __future__ import annotations

import asyncio
import threading
import uuid
from typing import TYPE_CHECKING
from typing import Any

from app.application.dtos.internal.vector_index import IndexedChunk
from app.application.dtos.internal.vector_index import VectorHit
from app.application.exceptions.processing import ProcessingError
from app.application.ports.vector_index import VectorIndexPort
from app.core.config import get_settings

if TYPE_CHECKING:
    from collections.abc import Sequence

_client_cache: dict[str, Any] = {}
_cache_lock = threading.Lock()

_CHUNK_ID_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "post-meeting-legal-analyzer.corpus")


def build_qdrant_client() -> Any:
    """Return a shared Qdrant client for the configured deployment mode.

    When ``QDRANT_LOCAL_PATH`` is set, an embedded file-backed client is
    used so no Qdrant server is required.  Clients are cached per target
    because embedded storage holds an exclusive lock on its directory.
    """
    from qdrant_client import QdrantClient

    settings = get_settings().qdrant
    key = f"local:{settings.local_path}" if settings.local_path else f"server:{settings.url}"

    with _cache_lock:
        client = _client_cache.get(key)
        if client is None:
            if settings.local_path:
                client = QdrantClient(path=settings.local_path)
            else:
                client = QdrantClient(
                    host=settings.host,
                    port=settings.port,
                    api_key=settings.api_key,
                )
            _client_cache[key] = client
    return client


def point_id_for_chunk(chunk_id: str) -> str:
    """Derive a deterministic UUID for a chunk so reindexing is idempotent."""
    return str(uuid.uuid5(_CHUNK_ID_NAMESPACE, chunk_id))


class QdrantVectorIndex(VectorIndexPort):
    """Concrete VectorIndexPort adapter backed by Qdrant.

    Works against a Qdrant server or the embedded local storage exposed by
    ``qdrant-client``.  The blocking client calls run in worker threads.
    """

    def __init__(
        self,
        collection_name: str,
        dimension: int,
        *,
        client: Any | None = None,
    ) -> None:
        self._collection_name = collection_name
        self._dimension = dimension
        self._client = client if client is not None else build_qdrant_client()

    @classmethod
    def from_settings(cls, *, client: Any | None = None) -> QdrantVectorIndex:
        settings = get_settings()
        return cls(
            collection_name=f"{settings.qdrant.collection_prefix}corpus",
            dimension=settings.ai.embedding_dimension,
            client=client,
        )

    async def upsert(self, items: Sequence[IndexedChunk]) -> None:
        if not items:
            return
        await asyncio.to_thread(self._upsert_sync, items)

    async def search(
        self,
        vector: Sequence[float],
        limit: int,
        *,
        matter_id: str | None = None,
        score_threshold: float | None = None,
    ) -> tuple[VectorHit, ...]:
        return await asyncio.to_thread(
            self._search_sync,
            vector,
            limit,
            matter_id,
            score_threshold,
        )

    def _upsert_sync(self, items: Sequence[IndexedChunk]) -> None:
        from qdrant_client.models import PointStruct

        self._ensure_collection_sync()
        points = [
            PointStruct(
                id=point_id_for_chunk(item.chunk_id),
                vector=list(item.vector),
                payload={
                    "chunk_id": item.chunk_id,
                    "matter_id": item.matter_id,
                    "source_id": item.source_id,
                    "text": item.text,
                    "page_number": item.page_number,
                    "start_offset": item.start_offset,
                    "end_offset": item.end_offset,
                },
            )
            for item in items
        ]
        try:
            self._client.upsert(collection_name=self._collection_name, points=points)
        except Exception as exc:
            raise ProcessingError(
                "vector_index_upsert",
                f"Qdrant upsert failed: {exc}",
            ) from exc

    def _search_sync(
        self,
        vector: Sequence[float],
        limit: int,
        matter_id: str | None,
        score_threshold: float | None,
    ) -> tuple[VectorHit, ...]:
        from qdrant_client.models import FieldCondition
        from qdrant_client.models import Filter
        from qdrant_client.models import MatchValue

        self._ensure_collection_sync()
        query_filter = None
        if matter_id is not None:
            query_filter = Filter(
                must=[FieldCondition(key="matter_id", match=MatchValue(value=matter_id))]
            )
        try:
            result = self._client.query_points(
                collection_name=self._collection_name,
                query=list(vector),
                limit=limit,
                query_filter=query_filter,
                score_threshold=score_threshold,
                with_payload=True,
            )
        except Exception as exc:
            raise ProcessingError(
                "vector_index_search",
                f"Qdrant search failed: {exc}",
            ) from exc

        hits: list[VectorHit] = []
        for point in result.points:
            payload = point.payload or {}
            hits.append(
                VectorHit(
                    chunk_id=str(payload.get("chunk_id", point.id)),
                    source_id=str(payload.get("source_id", "")),
                    text=str(payload.get("text", "")),
                    score=float(point.score),
                    page_number=payload.get("page_number"),
                    start_offset=payload.get("start_offset"),
                    end_offset=payload.get("end_offset"),
                )
            )
        return tuple(hits)

    def _ensure_collection_sync(self) -> None:
        from qdrant_client.models import Distance
        from qdrant_client.models import VectorParams

        try:
            if self._client.collection_exists(self._collection_name):
                info = self._client.get_collection(self._collection_name)
                vectors = info.config.params.vectors
                existing_size = getattr(vectors, "size", None)
                if existing_size is not None and existing_size != self._dimension:
                    raise ProcessingError(
                        "vector_index_collection",
                        (
                            f"Collection '{self._collection_name}' has dimension "
                            f"{existing_size} but expected {self._dimension}"
                        ),
                    )
                return
            self._client.create_collection(
                collection_name=self._collection_name,
                vectors_config=VectorParams(size=self._dimension, distance=Distance.COSINE),
            )
        except ProcessingError:
            raise
        except Exception as exc:
            raise ProcessingError(
                "vector_index_collection",
                f"Qdrant collection setup failed: {exc}",
            ) from exc
