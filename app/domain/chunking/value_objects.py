from __future__ import annotations

from dataclasses import dataclass

from app.domain.exceptions.invariant import InvariantViolation
from app.domain.shared.validation import ensure_not_blank
from app.domain.shared.value_object import ValueObject


@dataclass(frozen=True, slots=True)
class ChunkMetadata(ValueObject):
    """Immutable metadata describing the provenance of a text chunk."""

    source_type: str
    source_id: str
    speaker: str | None = None
    sequence_start: int | None = None
    sequence_end: int | None = None
    section_path: str | None = None
    page_number: int | None = None
    paragraph_number: int | None = None

    def __post_init__(self) -> None:
        normalized_source_type = ensure_not_blank(self.source_type, "source_type")
        object.__setattr__(self, "source_type", normalized_source_type)
        normalized_source_id = ensure_not_blank(self.source_id, "source_id")
        object.__setattr__(self, "source_id", normalized_source_id)

        if self.sequence_start is not None and self.sequence_start < 1:
            raise InvariantViolation("sequence_start must be positive", field_name="sequence_start")
        if self.sequence_end is not None and self.sequence_end < 1:
            raise InvariantViolation("sequence_end must be positive", field_name="sequence_end")
        if self.page_number is not None and self.page_number < 1:
            raise InvariantViolation("page_number must be positive", field_name="page_number")
        if self.paragraph_number is not None and self.paragraph_number < 1:
            raise InvariantViolation(
                "paragraph_number must be positive", field_name="paragraph_number"
            )

    def _equality_components(self) -> tuple[object, ...]:
        return (
            self.source_type,
            self.source_id,
            self.speaker,
            self.sequence_start,
            self.sequence_end,
            self.section_path,
            self.page_number,
            self.paragraph_number,
        )


@dataclass(frozen=True, slots=True)
class Chunk(ValueObject):
    """Immutable unit of semantically grouped text with provenance metadata."""

    text: str
    metadata: ChunkMetadata

    def __post_init__(self) -> None:
        normalized = ensure_not_blank(self.text, "text")
        object.__setattr__(self, "text", normalized)

    def _equality_components(self) -> tuple[object, ...]:
        return (self.text, self.metadata)
