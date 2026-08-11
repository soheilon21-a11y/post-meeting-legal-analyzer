from __future__ import annotations

import re
from dataclasses import dataclass

from app.domain.shared.validation import ensure_not_blank
from app.domain.shared.value_object import ValueObject


@dataclass(frozen=True, slots=True)
class MatterName(ValueObject):
    value: str

    def __post_init__(self) -> None:
        normalized = ensure_not_blank(self.value, "matter_name")
        if len(normalized) > 500:
            raise ValueError("matter_name must not exceed 500 characters")
        object.__setattr__(self, "value", normalized)

    def _equality_components(self) -> tuple[object, ...]:
        return (self.value.casefold(),)


@dataclass(frozen=True, slots=True)
class MatterNumber(ValueObject):
    value: str

    def __post_init__(self) -> None:
        normalized = ensure_not_blank(self.value, "matter_number")
        if len(normalized) > 100 or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]*", normalized):
            raise ValueError("matter_number contains invalid characters")
        object.__setattr__(self, "value", normalized)

    def _equality_components(self) -> tuple[object, ...]:
        return (self.value.casefold(),)
