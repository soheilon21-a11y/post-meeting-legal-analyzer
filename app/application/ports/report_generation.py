from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Protocol

if TYPE_CHECKING:
    from app.application.dtos.internal.report_generation import ReportGenerationInput
    from app.application.dtos.internal.report_generation import ReportGenerationResult


class ReportGenerationPort(Protocol):
    async def generate(self, request: ReportGenerationInput) -> ReportGenerationResult:
        """Generate report sections through an outer provider adapter."""
