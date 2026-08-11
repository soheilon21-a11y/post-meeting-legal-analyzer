from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Protocol

if TYPE_CHECKING:
    from app.application.dtos.internal.analysis_generation import AnalysisGenerationInput
    from app.application.dtos.internal.analysis_generation import AnalysisGenerationResult


class AnalysisGenerationPort(Protocol):
    async def generate(self, request: AnalysisGenerationInput) -> AnalysisGenerationResult:
        """Generate structured analysis through an outer local-model adapter."""
