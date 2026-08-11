from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID


@dataclass(frozen=True, slots=True)
class RedlineGenerationInput:
    redline_job_id: UUID
    base_document_id: UUID
    comparison_document_id: UUID
    deterministic_seed: int
    context_items: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class GeneratedRedlineCitation:
    source_id: str
    quote: str
    page_number: int | None = None
    start_offset: int | None = None
    end_offset: int | None = None


@dataclass(frozen=True, slots=True)
class GeneratedRedlineChange:
    clause_path: str
    change_type: str
    original_text: str
    proposed_text: str
    rationale: str
    risk_level: str
    confidence: float
    citations: tuple[GeneratedRedlineCitation, ...]


@dataclass(frozen=True, slots=True)
class RedlineGenerationResult:
    changes: tuple[GeneratedRedlineChange, ...]
