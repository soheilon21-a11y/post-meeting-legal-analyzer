from __future__ import annotations

from dataclasses import dataclass

from app.domain.shared.validation import ensure_not_blank
from app.domain.shared.value_object import ValueObject


@dataclass(frozen=True, slots=True)
class ReportTitle(ValueObject):
    value: str

    def __post_init__(self) -> None:
        normalized = ensure_not_blank(self.value, "report_title")
        if len(normalized) > 500:
            raise ValueError("report_title must not exceed 500 characters")
        object.__setattr__(self, "value", normalized)

    def _equality_components(self) -> tuple[object, ...]:
        return (self.value.casefold(),)
