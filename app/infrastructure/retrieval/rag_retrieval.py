from __future__ import annotations

from typing import TYPE_CHECKING

from app.application.exceptions.processing import ProcessingError
from app.application.ports.rag_retrieval import RetrievalPort
from app.core.logging import get_logger

if TYPE_CHECKING:
    from app.application.dtos.internal.analysis_generation import EvidenceInput
    from app.application.ports.embeddings import EmbeddingPort
    from app.application.ports.vector_index import VectorIndexPort

logger = get_logger(__name__)


class EmbeddedRetrieval(RetrievalPort):
    """Retrieval adapter that grounds evidence in a local vector index.

    Queries are embedded with the local embedding model and matched against
    indexed chunks.  If the embedding model or vector index is unavailable,
    the adapter degrades to empty evidence so that analysis remains usable;
    the degradation is logged for auditability.
    """

    def __init__(
        self,
        embeddings: EmbeddingPort,
        index: VectorIndexPort,
        *,
        score_threshold: float | None = None,
    ) -> None:
        self._embeddings = embeddings
        self._index = index
        self._score_threshold = score_threshold

    async def retrieve(
        self,
        matter_id: str,
        query: str,
        limit: int,
    ) -> tuple[EvidenceInput, ...]:
        from app.application.dtos.internal.analysis_generation import EvidenceInput

        try:
            vectors = await self._embeddings.embed((query,))
            if not vectors:
                return ()
            hits = await self._index.search(
                vectors[0],
                limit,
                matter_id=matter_id,
                score_threshold=self._score_threshold,
            )
        except ProcessingError as exc:
            logger.warning(
                "retrieval_degraded_to_empty_evidence",
                matter_id=matter_id,
                error=str(exc),
            )
            return ()

        return tuple(
            EvidenceInput(
                source_id=hit.source_id,
                quote=hit.text,
                page_number=hit.page_number,
                start_offset=hit.start_offset,
                end_offset=hit.end_offset,
            )
            for hit in hits
        )
