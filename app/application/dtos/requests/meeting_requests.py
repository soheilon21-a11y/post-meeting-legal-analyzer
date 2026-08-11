from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.application.exceptions.validation import ApplicationValidationError

if TYPE_CHECKING:
    from datetime import datetime

    from app.application.dtos.internal.security import ActorContext
    from app.domain.meeting.enums import MeetingSource


@dataclass(frozen=True, slots=True)
class CreateMeetingRequest:
    matter_id: str
    title: str
    meeting_date: datetime
    source: MeetingSource
    actor: ActorContext

    def __post_init__(self) -> None:
        if not self.matter_id.strip():
            raise ApplicationValidationError("Matter id must not be blank", field="matter_id")
        if not self.title.strip():
            raise ApplicationValidationError("Meeting title must not be blank", field="title")


@dataclass(frozen=True, slots=True)
class AddTranscriptSegmentRequest:
    meeting_id: str
    sequence_number: int
    text: str
    actor: ActorContext
    speaker: str | None = None
    start_seconds: float | None = None
    end_seconds: float | None = None

    def __post_init__(self) -> None:
        if self.sequence_number < 1:
            raise ApplicationValidationError(
                "Sequence number must be positive", field="sequence_number"
            )
        if not self.text.strip():
            raise ApplicationValidationError("Transcript text must not be blank", field="text")
