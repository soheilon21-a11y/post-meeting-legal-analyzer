from __future__ import annotations

from typing import TYPE_CHECKING

from app.application.dtos.internal.redline_generation import RedlineGenerationInput
from app.domain.analysis.value_objects import ConfidenceScore
from app.domain.analysis.value_objects import EvidenceQuote
from app.domain.analysis.value_objects import SourceLocation
from app.domain.exceptions.evidence import MissingEvidence
from app.domain.redlining.entities import RedlineChange
from app.domain.redlining.entities import RedlineJob
from app.domain.redlining.enums import ChangeType
from app.domain.redlining.value_objects import ClausePath
from app.domain.redlining.value_objects import ProposedText
from app.domain.redlining.value_objects import Rationale

if TYPE_CHECKING:
    from app.application.dtos.internal.redline_generation import GeneratedRedlineChange
    from app.application.dtos.internal.redline_generation import RedlineGenerationResult
    from app.application.ports.redline_generation import RedlineGenerationPort
    from app.application.services.context_optimizer import ContextOptimizer


class RedlineApplicationService:
    """Converts deterministic provider output into review-only domain changes."""

    def __init__(
        self,
        generation: RedlineGenerationPort,
        *,
        optimizer: ContextOptimizer | None = None,
        model_name: str = "default",
        max_input: int | None = None,
        reserved_output: int = 0,
    ) -> None:
        self._generation = generation
        self._optimizer = optimizer
        self._model_name = model_name
        self._max_input = max_input
        self._reserved_output = reserved_output

    async def generate(
        self,
        job: RedlineJob,
        request: RedlineGenerationInput,
    ) -> None:
        if self._optimizer is not None and request.context_items:
            optimized = await self._optimizer.optimize(
                request.context_items,
                model_name=self._model_name,
                max_input=self._max_input,
                reserved_output=self._reserved_output,
            )
            request = RedlineGenerationInput(
                redline_job_id=request.redline_job_id,
                base_document_id=request.base_document_id,
                comparison_document_id=request.comparison_document_id,
                deterministic_seed=request.deterministic_seed,
                context_items=optimized.items,
            )
        result = await self._generation.generate(request)
        self.apply_result(job, result)

    def apply_result(self, job: RedlineJob, result: RedlineGenerationResult) -> None:
        job.begin_processing()
        for change in result.changes:
            self._validate_change(change)
            job.add_change(
                RedlineChange(
                    clause_path=ClausePath(change.clause_path),
                    change_type=ChangeType(change.change_type),
                    original_text=change.original_text,
                    proposed_text=ProposedText(change.proposed_text),
                    rationale=Rationale(change.rationale),
                    confidence=ConfidenceScore(change.confidence),
                    citations=self._citations(change),
                    risk_level=change.risk_level,
                )
            )
        job.mark_ready_for_review()

    @staticmethod
    def _validate_change(change: GeneratedRedlineChange) -> None:
        if not change.original_text.strip():
            raise ValueError("Generated redline original text is required")
        if change.original_text.strip() == change.proposed_text.strip():
            raise ValueError("Generated redline must modify, never replace, original text")
        if not change.rationale.strip():
            raise ValueError("Generated redline rationale is required")
        if not change.risk_level.strip():
            raise ValueError("Generated redline risk level is required")
        if not change.citations:
            raise MissingEvidence("redline change", ["supporting citation"])

    @staticmethod
    def _citations(
        change: GeneratedRedlineChange,
    ) -> tuple[EvidenceQuote | SourceLocation, ...]:
        return tuple(
            value
            for citation in change.citations
            for value in (
                EvidenceQuote(citation.quote),
                SourceLocation(
                    source_id=citation.source_id,
                    page_number=citation.page_number,
                    start_offset=citation.start_offset,
                    end_offset=citation.end_offset,
                ),
            )
        )
