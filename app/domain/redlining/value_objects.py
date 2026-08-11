from __future__ import annotations

from dataclasses import dataclass

from app.domain.shared.validation import ensure_not_blank
from app.domain.shared.value_object import ValueObject


@dataclass(frozen=True, slots=True)
class ClausePath(ValueObject):
    value: str

    def __post_init__(self) -> None:
        normalized = ensure_not_blank(self.value, "clause_path")
        if len(normalized) > 1000:
            raise ValueError("clause_path must not exceed 1000 characters")
        object.__setattr__(self, "value", normalized)

    def _equality_components(self) -> tuple[object, ...]:
        return (self.value,)


@dataclass(frozen=True, slots=True)
class ProposedText(ValueObject):
    value: str

    def __post_init__(self) -> None:
        normalized = self.value.strip()
        if not normalized:
            raise ValueError("proposed_text must not be blank")
        object.__setattr__(self, "value", normalized)

    def _equality_components(self) -> tuple[object, ...]:
        return (self.value,)


@dataclass(frozen=True, slots=True)
class Rationale(ValueObject):
    value: str

    def __post_init__(self) -> None:
        normalized = ensure_not_blank(self.value, "rationale")
        object.__setattr__(self, "value", normalized)

    def _equality_components(self) -> tuple[object, ...]:
        return (self.value,)
