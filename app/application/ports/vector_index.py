from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Protocol
from typing import runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.application.dtos.internal.vector_index import IndexedChunk
    from app.application.dtos.internal.vector_index import VectorHit


@runtime_checkable
class VectorIndexPort(Protocol):
    """Abstract vector store for upserting and searching embedded chunks."""

    async def upsert(self, items: Sequence[IndexedChunk]) -> None:
        """Insert or update embedded chunks in the index."""

    async def search(
        self,
        vector: Sequence[float],
        limit: int,
        *,
        matter_id: str | None = None,
        score_threshold: float | None = None,
    ) -> tuple[VectorHit, ...]:
        """Return the closest indexed chunks for the query vector."""
