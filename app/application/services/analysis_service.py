from __future__ import annotations

from typing import TYPE_CHECKING

from app.application.dtos.internal.analysis_generation import AnalysisGenerationInput
from app.application.dtos.internal.analysis_generation import AnalysisGenerationResult
from app.application.dtos.internal.analysis_generation import EvidenceInput
from app.domain.analysis.entities import ActionItem
from app.domain.analysis.entities import Citation
from app.domain.analysis.entities import Deadline
from app.domain.analysis.entities import LegalAnalysis
from app.domain.analysis.entities import Obligation
from app.domain.analysis.entities import Risk
from app.domain.analysis.enums import RiskLevel
from app.domain.analysis.value_objects import ConfidenceScore
from app.domain.analysis.value_objects import Deadline as DeadlineValue
from app.domain.analysis.value_objects import EvidenceQuote
from app.domain.analysis.value_objects import ResponsibleParty
from app.domain.analysis.value_objects import SourceLocation

if TYPE_CHECKING:
    from datetime import date

    from app.application.ports.llm_generation import AnalysisGenerationPort
    from app.application.ports.rag_retrieval import RetrievalPort
    from app.application.services.context_optimizer import ContextOptimizer
    from app.domain.meeting.entities import Meeting
    from app.domain.ports.event_dispatcher import EventDispatcher


class AnalysisApplicationService:
    """Coordinates retrieval, generation, and conversion into domain items."""

    def __init__(
        self,
        retrieval: RetrievalPort,
        generation: AnalysisGenerationPort,
        *,
        optimizer: ContextOptimizer | None = None,
        model_name: str = "default",
        max_input: int | None = None,
        reserved_output: int = 0,
        matter_id: str | None = None,
        event_dispatcher: EventDispatcher | None = None,
    ) -> None:
        self._retrieval = retrieval
        self._generation = generation
        self._optimizer = optimizer
        self._model_name = model_name
        self._max_input = max_input
        self._reserved_output = reserved_output
        self._matter_id = matter_id
        self._event_dispatcher = event_dispatcher

    async def execute(self, analysis: LegalAnalysis, meeting: Meeting) -> None:
        analysis.begin_processing()
        transcript = "\n".join(segment.text for segment in meeting.transcript)
        retrieval_scope = self._matter_id or str(analysis.id)
        evidence = await self._retrieval.retrieve(retrieval_scope, transcript, limit=20)

        if self._optimizer is not None:
            optimized = await self._optimizer.optimize(
                [transcript] + [e.quote for e in evidence],
                model_name=self._model_name,
                max_input=self._max_input,
                reserved_output=self._reserved_output,
            )
            kept_count = len(optimized.items)
            transcript = optimized.items[0] if kept_count > 0 else ""
            kept_evidence_count = max(0, kept_count - 1)
            evidence = evidence[:kept_evidence_count]

        result = await self._generation.generate(
            AnalysisGenerationInput(
                analysis_id=analysis.id,
                meeting_id=meeting.id,
                transcript=transcript,
                evidence=evidence,
                analysis_type=analysis.analysis_type.value,
            )
        )
        self.apply_result(analysis, result)
        if self._event_dispatcher is not None:
            await self._event_dispatcher.dispatch_many(analysis.pull_events())

    def apply_result(self, analysis: LegalAnalysis, result: AnalysisGenerationResult) -> None:
        for risk in result.risks:
            analysis.add_item(
                Risk(
                    title=risk.title,
                    description=risk.description,
                    level=RiskLevel(risk.level),
                    confidence=ConfidenceScore(risk.confidence),
                    citations=self._citations(risk.evidence),
                )
            )
        for obligation in result.obligations:
            analysis.add_item(
                Obligation(
                    title=obligation.title,
                    description=obligation.description,
                    responsible_party=ResponsibleParty(obligation.responsible_party),
                    deadline=self._deadline(obligation.due_date, obligation.responsible_party),
                    confidence=ConfidenceScore(obligation.confidence),
                    citations=self._citations(obligation.evidence),
                )
            )
        for action in result.action_items:
            analysis.add_item(
                ActionItem(
                    title=action.title,
                    description=action.description,
                    responsible_party=ResponsibleParty(action.responsible_party),
                    deadline=self._deadline(action.due_date, action.responsible_party),
                    confidence=ConfidenceScore(action.confidence),
                    citations=self._citations(action.evidence),
                )
            )
        analysis.set_summary(result.summary)
        analysis.mark_ready_for_review()

    @staticmethod
    def _citations(evidence: tuple[EvidenceInput, ...]) -> tuple[Citation, ...]:
        return tuple(
            Citation(
                quote=EvidenceQuote(item.quote),
                location=SourceLocation(
                    source_id=item.source_id,
                    page_number=item.page_number,
                    start_offset=item.start_offset,
                    end_offset=item.end_offset,
                ),
            )
            for item in evidence
        )

    @staticmethod
    def _deadline(due_date: date | None, responsible_party: str) -> Deadline | None:
        if due_date is None:
            return None
        return Deadline(DeadlineValue(due_date), ResponsibleParty(responsible_party))
