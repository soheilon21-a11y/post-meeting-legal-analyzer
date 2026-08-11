from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import date
    from uuid import UUID


@dataclass(frozen=True, slots=True)
class CitationResponse:
    id: UUID
    quote: str
    source_id: str
    page_number: int | None
    start_offset: int | None
    end_offset: int | None


@dataclass(frozen=True, slots=True)
class EvidenceResponse:
    source_id: str
    quote: str
    page_number: int | None
    start_offset: int | None
    end_offset: int | None


@dataclass(frozen=True, slots=True)
class AnalysisItemResponse:
    id: UUID
    item_type: str
    title: str
    description: str
    status: str
    confidence: float
    risk_level: str | None
    responsible_party: str | None
    due_date: date | None
    citations: tuple[CitationResponse, ...]


@dataclass(frozen=True, slots=True)
class AnalysisResponse:
    id: UUID
    analysis_type: str
    status: str
    summary: str | None
    items: tuple[AnalysisItemResponse, ...]


@dataclass(frozen=True, slots=True)
class AnalysisJobResponse:
    analysis_id: UUID
    job_id: UUID
    status: str
