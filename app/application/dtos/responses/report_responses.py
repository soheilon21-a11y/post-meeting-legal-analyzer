from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID


@dataclass(frozen=True, slots=True)
class ReportSectionResponse:
    id: UUID
    heading: str
    content: str
    sequence_number: int


@dataclass(frozen=True, slots=True)
class ReportResponse:
    id: UUID
    title: str
    status: str
    sections: tuple[ReportSectionResponse, ...]
    exported_formats: frozenset[str]
