from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID


@dataclass(frozen=True, slots=True)
class ReportGenerationInput:
    report_id: UUID
    analysis_id: UUID
    title: str
    context_items: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class GeneratedReportSection:
    heading: str
    content: str


@dataclass(frozen=True, slots=True)
class ReportGenerationResult:
    sections: tuple[GeneratedReportSection, ...]
