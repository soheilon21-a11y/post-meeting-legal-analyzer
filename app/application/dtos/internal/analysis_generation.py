from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import date
    from uuid import UUID


@dataclass(frozen=True, slots=True)
class EvidenceInput:
    source_id: str
    quote: str
    page_number: int | None = None
    start_offset: int | None = None
    end_offset: int | None = None


@dataclass(frozen=True, slots=True)
class GeneratedRisk:
    title: str
    description: str
    level: str
    confidence: float
    evidence: tuple[EvidenceInput, ...]


@dataclass(frozen=True, slots=True)
class GeneratedObligation:
    title: str
    description: str
    responsible_party: str
    confidence: float
    evidence: tuple[EvidenceInput, ...]
    due_date: date | None = None


@dataclass(frozen=True, slots=True)
class GeneratedActionItem:
    title: str
    description: str
    responsible_party: str
    confidence: float
    evidence: tuple[EvidenceInput, ...] = ()
    due_date: date | None = None


@dataclass(frozen=True, slots=True)
class AnalysisGenerationInput:
    analysis_id: UUID
    meeting_id: UUID
    transcript: str
    evidence: tuple[EvidenceInput, ...]
    analysis_type: str


@dataclass(frozen=True, slots=True)
class AnalysisGenerationResult:
    summary: str
    risks: tuple[GeneratedRisk, ...] = ()
    obligations: tuple[GeneratedObligation, ...] = ()
    action_items: tuple[GeneratedActionItem, ...] = ()
