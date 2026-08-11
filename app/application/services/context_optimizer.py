from __future__ import annotations

from typing import TYPE_CHECKING

from app.application.dtos.internal.optimized_context import OptimizedContextResult
from app.domain.ai.services.token_optimizer import TokenOptimizer
from app.domain.ai.value_objects import TokenBudget
from app.domain.ai.value_objects import TokenCount

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.application.ports.tokenization import ContextWindowPort
    from app.application.ports.tokenization import TokenizerPort


class ContextOptimizer:
    """Application-level orchestrator for fitting context to a token budget.

    Coordinates the tokenizer port, context-window port, and the pure
    domain `TokenOptimizer` policy. It does not contain optimization
    rules itself; it only counts, validates, and delegates.
    """

    def __init__(
        self,
        tokenizer: TokenizerPort,
        context_window: ContextWindowPort,
        optimizer: TokenOptimizer | None = None,
    ) -> None:
        self._tokenizer = tokenizer
        self._context_window = context_window
        self._optimizer = optimizer or TokenOptimizer()

    async def optimize(
        self,
        context_items: Sequence[str],
        model_name: str,
        max_input: int | None = None,
        reserved_output: int = 0,
    ) -> OptimizedContextResult:
        """Count tokens, validate budget, and return the domain-optimized context."""
        window = await self._context_window.capacity(model_name)

        if max_input is None:
            max_input = window.capacity
        budget = TokenBudget(max_input=max_input, reserved_output=reserved_output)
        window.require_fit(budget)

        counted_items: list[tuple[str, TokenCount]] = []
        original_total = 0
        for item in context_items:
            count = await self._tokenizer.count(item)
            counted_items.append((item, count))
            original_total += count.value

        result = self._optimizer.optimize(counted_items, budget)

        return OptimizedContextResult(
            items=result.items,
            decision=result.decision,
            original_token_count=TokenCount(original_total),
            optimized_token_count=result.total_tokens,
            model_name=model_name,
            context_window_capacity=window.capacity,
        )
