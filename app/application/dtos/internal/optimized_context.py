from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.domain.ai.services.token_optimizer import OptimizationDecision
    from app.domain.ai.value_objects import TokenCount


@dataclass(frozen=True, slots=True)
class OptimizedContextResult:
    """Immutable application-level result of context optimization."""

    items: tuple[str, ...]
    decision: OptimizationDecision
    original_token_count: TokenCount
    optimized_token_count: TokenCount
    model_name: str
    context_window_capacity: int
