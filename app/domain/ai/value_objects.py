from __future__ import annotations

from dataclasses import dataclass

from app.domain.exceptions.invariant import InvariantViolation
from app.domain.shared.validation import ensure_non_negative
from app.domain.shared.validation import ensure_positive
from app.domain.shared.value_object import ValueObject


@dataclass(frozen=True, slots=True)
class TokenCount(ValueObject):
    """Immutable non-negative token count."""

    value: int

    def __post_init__(self) -> None:
        ensure_non_negative(self.value, "token_count")

    def _equality_components(self) -> tuple[object, ...]:
        return (self.value,)

    def __add__(self, other: TokenCount) -> TokenCount:
        return TokenCount(self.value + other.value)

    def __sub__(self, other: TokenCount) -> TokenCount:
        if other.value > self.value:
            raise InvariantViolation("token subtraction would underflow", field_name="token_count")
        return TokenCount(self.value - other.value)

    def __lt__(self, other: TokenCount) -> bool:
        return self.value < other.value

    def __le__(self, other: TokenCount) -> bool:
        return self.value <= other.value

    def __gt__(self, other: TokenCount) -> bool:
        return self.value > other.value

    def __ge__(self, other: TokenCount) -> bool:
        return self.value >= other.value


@dataclass(frozen=True, slots=True)
class TokenBudget(ValueObject):
    """Allowed token budget separating input capacity from reserved output."""

    max_input: int
    reserved_output: int = 0

    def __post_init__(self) -> None:
        ensure_positive(self.max_input, "max_input")
        ensure_non_negative(self.reserved_output, "reserved_output")
        if self.reserved_output >= self.max_input:
            raise InvariantViolation(
                "reserved_output must be less than max_input",
                field_name="reserved_output",
            )

    def _equality_components(self) -> tuple[object, ...]:
        return (self.max_input, self.reserved_output)

    @property
    def available_for_input(self) -> int:
        return self.max_input - self.reserved_output


@dataclass(frozen=True, slots=True)
class ContextWindow(ValueObject):
    """Model context-window capacity with budget-fit validation."""

    capacity: int

    def __post_init__(self) -> None:
        ensure_positive(self.capacity, "capacity")

    def _equality_components(self) -> tuple[object, ...]:
        return (self.capacity,)

    def fits(self, budget: TokenBudget) -> bool:
        return budget.max_input <= self.capacity

    def require_fit(self, budget: TokenBudget) -> None:
        if not self.fits(budget):
            raise InvariantViolation(
                f"token budget ({budget.max_input}) exceeds context window ({self.capacity})",
                field_name="token_budget",
            )
