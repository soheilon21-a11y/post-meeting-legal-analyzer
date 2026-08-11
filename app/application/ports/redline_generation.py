from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Protocol

if TYPE_CHECKING:
    from app.application.dtos.internal.redline_generation import RedlineGenerationInput
    from app.application.dtos.internal.redline_generation import RedlineGenerationResult


class RedlineGenerationPort(Protocol):
    async def generate(self, request: RedlineGenerationInput) -> RedlineGenerationResult:
        """Generate deterministic proposed changes through an outer adapter."""
