from __future__ import annotations

import pytest

from app.domain.ai.services.token_optimizer import OptimizationDecision
from app.domain.ai.services.token_optimizer import TokenOptimizer
from app.domain.ai.value_objects import ContextWindow
from app.domain.ai.value_objects import TokenBudget
from app.domain.ai.value_objects import TokenCount
from app.domain.exceptions.invariant import InvariantViolation


class TestTokenCount:
    def test_valid_positive(self) -> None:
        tc = TokenCount(42)
        assert tc.value == 42

    def test_valid_zero(self) -> None:
        tc = TokenCount(0)
        assert tc.value == 0

    def test_negative_rejected(self) -> None:
        with pytest.raises(InvariantViolation):
            TokenCount(-1)

    def test_equality(self) -> None:
        assert TokenCount(10) == TokenCount(10)
        assert TokenCount(10) != TokenCount(11)

    def test_addition(self) -> None:
        assert TokenCount(3) + TokenCount(5) == TokenCount(8)

    def test_subtraction(self) -> None:
        assert TokenCount(8) - TokenCount(5) == TokenCount(3)

    def test_subtraction_underflow_rejected(self) -> None:
        with pytest.raises(InvariantViolation):
            TokenCount(2) - TokenCount(5)

    def test_comparison(self) -> None:
        assert TokenCount(1) < TokenCount(2)
        assert TokenCount(2) <= TokenCount(2)
        assert TokenCount(3) > TokenCount(2)
        assert TokenCount(3) >= TokenCount(3)


class TestTokenBudget:
    def test_valid(self) -> None:
        budget = TokenBudget(1000, 200)
        assert budget.max_input == 1000
        assert budget.reserved_output == 200
        assert budget.available_for_input == 800

    def test_valid_no_reserved(self) -> None:
        budget = TokenBudget(512)
        assert budget.reserved_output == 0
        assert budget.available_for_input == 512

    def test_zero_max_input_rejected(self) -> None:
        with pytest.raises(InvariantViolation):
            TokenBudget(0)

    def test_negative_reserved_rejected(self) -> None:
        with pytest.raises(InvariantViolation):
            TokenBudget(100, -1)

    def test_reserved_equals_max_rejected(self) -> None:
        with pytest.raises(InvariantViolation, match="reserved_output must be less than max_input"):
            TokenBudget(100, 100)

    def test_reserved_exceeds_max_rejected(self) -> None:
        with pytest.raises(InvariantViolation, match="reserved_output must be less than max_input"):
            TokenBudget(100, 150)


class TestContextWindow:
    def test_valid(self) -> None:
        cw = ContextWindow(4096)
        assert cw.capacity == 4096

    def test_zero_rejected(self) -> None:
        with pytest.raises(InvariantViolation):
            ContextWindow(0)

    def test_negative_rejected(self) -> None:
        with pytest.raises(InvariantViolation):
            ContextWindow(-1)

    def test_fits_when_budget_within(self) -> None:
        assert ContextWindow(100).fits(TokenBudget(80)) is True

    def test_fits_when_budget_equal(self) -> None:
        assert ContextWindow(100).fits(TokenBudget(100)) is True

    def test_does_not_fit_when_budget_exceeds(self) -> None:
        assert ContextWindow(100).fits(TokenBudget(120)) is False

    def test_require_fit_passes(self) -> None:
        ContextWindow(100).require_fit(TokenBudget(80))

    def test_require_fit_raises(self) -> None:
        with pytest.raises(InvariantViolation, match="exceeds context window"):
            ContextWindow(100).require_fit(TokenBudget(120))


class TestTokenOptimizer:
    def test_keep_when_within_budget(self) -> None:
        optimizer = TokenOptimizer()
        result = optimizer.optimize(
            [("a", TokenCount(10)), ("b", TokenCount(20))],
            TokenBudget(100),
        )
        assert result.decision is OptimizationDecision.KEEP
        assert result.items == ("a", "b")
        assert result.total_tokens == TokenCount(30)

    def test_exclude_lower_priority_when_over_budget(self) -> None:
        optimizer = TokenOptimizer()
        result = optimizer.optimize(
            [
                ("high", TokenCount(60)),
                ("medium", TokenCount(30)),
                ("low", TokenCount(20)),
            ],
            TokenBudget(100),
        )
        assert result.decision is OptimizationDecision.EXCLUDE
        assert result.items == ("high", "medium")
        assert result.total_tokens == TokenCount(90)

    def test_reject_when_first_item_exceeds_budget(self) -> None:
        optimizer = TokenOptimizer()
        result = optimizer.optimize(
            [("too_large", TokenCount(200))],
            TokenBudget(100),
        )
        assert result.decision is OptimizationDecision.REJECT
        assert result.items == ()
        assert result.total_tokens == TokenCount(0)

    def test_respects_reserved_output(self) -> None:
        optimizer = TokenOptimizer()
        result = optimizer.optimize(
            [("a", TokenCount(40)), ("b", TokenCount(30))],
            TokenBudget(100, reserved_output=50),
        )
        # available_for_input is 50, so only "a" fits
        assert result.decision is OptimizationDecision.EXCLUDE
        assert result.items == ("a",)
        assert result.total_tokens == TokenCount(40)

    def test_empty_context_keep(self) -> None:
        optimizer = TokenOptimizer()
        result = optimizer.optimize([], TokenBudget(100))
        assert result.decision is OptimizationDecision.KEEP
        assert result.items == ()
        assert result.total_tokens == TokenCount(0)

    def test_exact_budget_boundary(self) -> None:
        optimizer = TokenOptimizer()
        result = optimizer.optimize(
            [("a", TokenCount(50)), ("b", TokenCount(50))],
            TokenBudget(100),
        )
        assert result.decision is OptimizationDecision.KEEP
        assert result.items == ("a", "b")
        assert result.total_tokens == TokenCount(100)

    def test_partial_fit_excludes(self) -> None:
        optimizer = TokenOptimizer()
        result = optimizer.optimize(
            [
                ("a", TokenCount(30)),
                ("b", TokenCount(30)),
                ("c", TokenCount(30)),
                ("d", TokenCount(30)),
            ],
            TokenBudget(100),
        )
        assert result.decision is OptimizationDecision.EXCLUDE
        assert result.items == ("a", "b", "c")
        assert result.total_tokens == TokenCount(90)
