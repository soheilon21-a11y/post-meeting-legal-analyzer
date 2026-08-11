from __future__ import annotations

from typing import TYPE_CHECKING

from app.application.ports.rag_retrieval import RetrievalPort

if TYPE_CHECKING:
    from app.application.dtos.internal.analysis_generation import EvidenceInput


class NoOpRetrieval(RetrievalPort):
    """Retrieval adapter that returns empty evidence.

    Suitable for MVP demos where RAG infrastructure is not yet wired.
    """

    async def retrieve(
        self,
        matter_id: str,
        query: str,
        limit: int,
    ) -> tuple[EvidenceInput, ...]:
        return ()
