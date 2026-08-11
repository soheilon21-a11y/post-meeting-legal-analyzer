from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Protocol

if TYPE_CHECKING:
    from app.application.dtos.internal.analysis_generation import EvidenceInput


class RetrievalPort(Protocol):
    async def retrieve(
        self,
        matter_id: str,
        query: str,
        limit: int,
    ) -> tuple[EvidenceInput, ...]:
        """Retrieve grounded evidence through an outer RAG adapter."""
