from __future__ import annotations

from dataclasses import dataclass

from app.domain.shared.validation import ensure_non_negative
from app.domain.shared.validation import ensure_not_blank
from app.domain.shared.value_object import ValueObject


@dataclass(frozen=True, slots=True)
class OrganizationName(ValueObject):
    value: str

    def __post_init__(self) -> None:
        normalized = ensure_not_blank(self.value, "organization_name")
        if len(normalized) > 255:
            raise ValueError("organization_name must not exceed 255 characters")
        object.__setattr__(self, "value", normalized)

    def _equality_components(self) -> tuple[object, ...]:
        return (self.value.casefold(),)


@dataclass(frozen=True, slots=True)
class RetentionPolicy(ValueObject):
    days: int | None

    def __post_init__(self) -> None:
        if self.days is not None:
            ensure_non_negative(self.days, "retention_days")

    def _equality_components(self) -> tuple[object, ...]:
        return (self.days,)

    @property
    def is_indefinite(self) -> bool:
        return self.days is None
