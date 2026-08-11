from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID


@dataclass(frozen=True, slots=True)
class TranscriptSegmentResponse:
    id: UUID
    sequence_number: int
    text: str
    speaker: str | None
    start_seconds: float | None
    end_seconds: float | None


@dataclass(frozen=True, slots=True)
class MeetingResponse:
    id: UUID
    title: str
    meeting_date: datetime
    source: str
    status: str
    transcript: tuple[TranscriptSegmentResponse, ...]
