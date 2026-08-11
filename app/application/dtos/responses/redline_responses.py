from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID


@dataclass(frozen=True, slots=True)
class RedlineCitationResponse:
    source_id: str
    quote: str
    page_number: int | None
    start_offset: int | None
    end_offset: int | None


@dataclass(frozen=True, slots=True)
class RedlineChangeResponse:
    id: UUID
    clause_path: str
    change_type: str
    original_text: str
    proposed_text: str
    rationale: str
    risk_level: str
    confidence: float
    review_status: str
    citations: tuple[RedlineCitationResponse, ...]


@dataclass(frozen=True, slots=True)
class RedlineResponse:
    id: UUID
    status: str
    changes: tuple[RedlineChangeResponse, ...]
