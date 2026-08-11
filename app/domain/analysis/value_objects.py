from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.domain.shared.validation import ensure_in_range
from app.domain.shared.validation import ensure_not_blank
from app.domain.shared.value_object import ValueObject

if TYPE_CHECKING:
    from datetime import date


@dataclass(frozen=True, slots=True)
class ConfidenceScore(ValueObject):
    value: float

    def __post_init__(self) -> None:
        ensure_in_range(self.value, 0.0, 1.0, "confidence_score")

    def _equality_components(self) -> tuple[object, ...]:
        return (self.value,)


@dataclass(frozen=True, slots=True)
class ResponsibleParty(ValueObject):
    value: str

    def __post_init__(self) -> None:
        normalized = ensure_not_blank(self.value, "responsible_party")
        if len(normalized) > 500:
            raise ValueError("responsible_party must not exceed 500 characters")
        object.__setattr__(self, "value", normalized)

    def _equality_components(self) -> tuple[object, ...]:
        return (self.value.casefold(),)


@dataclass(frozen=True, slots=True)
class EvidenceQuote(ValueObject):
    value: str

    def __post_init__(self) -> None:
        normalized = ensure_not_blank(self.value, "evidence_quote")
        if len(normalized) > 10000:
            raise ValueError("evidence_quote must not exceed 10000 characters")
        object.__setattr__(self, "value", normalized)

    def _equality_components(self) -> tuple[object, ...]:
        return (self.value,)


@dataclass(frozen=True, slots=True)
class SourceLocation(ValueObject):
    source_id: str
    page_number: int | None = None
    start_offset: int | None = None
    end_offset: int | None = None

    def __post_init__(self) -> None:
        ensure_not_blank(self.source_id, "source_id")
        if self.page_number is not None and self.page_number < 1:
            raise ValueError("page_number must be positive")
        if self.start_offset is not None and self.start_offset < 0:
            raise ValueError("start_offset must not be negative")
        if self.end_offset is not None and self.end_offset < 0:
            raise ValueError("end_offset must not be negative")
        if (
            self.start_offset is not None
            and self.end_offset is not None
            and self.end_offset < self.start_offset
        ):
            raise ValueError("end_offset must not precede start_offset")

    def _equality_components(self) -> tuple[object, ...]:
        return (self.source_id, self.page_number, self.start_offset, self.end_offset)


@dataclass(frozen=True, slots=True)
class Deadline(ValueObject):
    value: date

    def _equality_components(self) -> tuple[object, ...]:
        return (self.value,)
