from __future__ import annotations

from typing import TYPE_CHECKING

from app.application.dtos.internal.report_generation import ReportGenerationInput
from app.domain.reporting.entities import LegalReport
from app.domain.reporting.entities import ReportSection

if TYPE_CHECKING:
    from app.application.ports.report_generation import ReportGenerationPort
    from app.application.services.context_optimizer import ContextOptimizer


class ReportApplicationService:
    """Converts provider output into ordered report sections."""

    def __init__(
        self,
        generation: ReportGenerationPort,
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

    async def generate(self, report: LegalReport, request: ReportGenerationInput) -> None:
        if self._optimizer is not None and request.context_items:
            optimized = await self._optimizer.optimize(
                request.context_items,
                model_name=self._model_name,
                max_input=self._max_input,
                reserved_output=self._reserved_output,
            )
            request = ReportGenerationInput(
                report_id=request.report_id,
                analysis_id=request.analysis_id,
                title=request.title,
                context_items=optimized.items,
            )
        result = await self._generation.generate(request)
        report.begin_generation()
        for sequence, section in enumerate(result.sections, start=1):
            report.add_section(ReportSection(section.heading, section.content, sequence))
        report.mark_ready()
