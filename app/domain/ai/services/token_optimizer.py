from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from app.domain.ai.value_objects import TokenBudget
from app.domain.ai.value_objects import TokenCount

if TYPE_CHECKING:
    from collections.abc import Sequence


class OptimizationDecision(StrEnum):
    """Deterministic policy outcome when fitting context to a token budget."""

    KEEP = "keep"
    TRUNCATE = "truncate"
    EXCLUDE = "exclude"
    REJECT = "reject"


@dataclass(frozen=True, slots=True)
class OptimizedContext:
    """Result of applying the token-optimization policy to a context list."""

    items: tuple[str, ...]
    decision: OptimizationDecision
    total_tokens: TokenCount
    budget: TokenBudget


class TokenOptimizer:
    """Pure domain policy for fitting context items into a token budget.

    The optimizer receives pre-counted context items ordered by priority
    (highest first) and decides which items to retain. It does not perform
    tokenization, summarization, or LLM calls.
    """

    def optimize(
        self,
        context_items: Sequence[tuple[str, TokenCount]],
        budget: TokenBudget,
    ) -> OptimizedContext:
        limit = budget.available_for_input
        kept: list[str] = []
        total = 0

        for text, count in context_items:
            if total + count.value <= limit:
                kept.append(text)
                total += count.value
            else:
                break

        if not kept and context_items:
            return OptimizedContext(
                items=(),
                decision=OptimizationDecision.REJECT,
                total_tokens=TokenCount(0),
                budget=budget,
            )

        if len(kept) == len(context_items):
            decision = OptimizationDecision.KEEP
        else:
            decision = OptimizationDecision.EXCLUDE

        return OptimizedContext(
            items=tuple(kept),
            decision=decision,
            total_tokens=TokenCount(total),
            budget=budget,
        )
