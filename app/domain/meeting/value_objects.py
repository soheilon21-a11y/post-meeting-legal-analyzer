from __future__ import annotations

from dataclasses import dataclass

from app.domain.shared.validation import ensure_non_negative
from app.domain.shared.validation import ensure_not_blank
from app.domain.shared.value_object import ValueObject


@dataclass(frozen=True, slots=True)
class MeetingTitle(ValueObject):
    value: str

    def __post_init__(self) -> None:
        normalized = ensure_not_blank(self.value, "meeting_title")
        if len(normalized) > 500:
            raise ValueError("meeting_title must not exceed 500 characters")
        object.__setattr__(self, "value", normalized)

    def _equality_components(self) -> tuple[object, ...]:
        return (self.value.casefold(),)


@dataclass(frozen=True, slots=True)
class Speaker(ValueObject):
    value: str

    def __post_init__(self) -> None:
        normalized = ensure_not_blank(self.value, "speaker")
        if len(normalized) > 255:
            raise ValueError("speaker must not exceed 255 characters")
        object.__setattr__(self, "value", normalized)

    def _equality_components(self) -> tuple[object, ...]:
        return (self.value.casefold(),)


@dataclass(frozen=True, slots=True)
class TranscriptTimestamp(ValueObject):
    start_seconds: float
    end_seconds: float

    def __post_init__(self) -> None:
        ensure_non_negative(self.start_seconds, "start_seconds")
        ensure_non_negative(self.end_seconds, "end_seconds")
        if self.end_seconds < self.start_seconds:
            raise ValueError("end_seconds must not precede start_seconds")

    def _equality_components(self) -> tuple[object, ...]:
        return (self.start_seconds, self.end_seconds)
