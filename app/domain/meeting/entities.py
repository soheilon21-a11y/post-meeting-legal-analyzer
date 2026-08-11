from __future__ import annotations

from typing import TYPE_CHECKING

from app.domain.exceptions.invariant import InvariantViolation
from app.domain.exceptions.lifecycle import InvalidStateTransition
from app.domain.meeting.enums import MeetingSource
from app.domain.meeting.enums import MeetingStatus
from app.domain.meeting.rules import ensure_meeting_can_be_archived
from app.domain.meeting.rules import ensure_meeting_can_receive_transcript
from app.domain.shared.aggregate_root import AggregateRoot
from app.domain.shared.entity import Entity
from app.domain.shared.identifiers import MeetingId

if TYPE_CHECKING:
    from datetime import datetime

    from app.domain.meeting.value_objects import MeetingTitle
    from app.domain.meeting.value_objects import Speaker
    from app.domain.meeting.value_objects import TranscriptTimestamp


class TranscriptSegment(Entity[MeetingId]):
    def __init__(
        self,
        sequence_number: int,
        text: str,
        speaker: Speaker | None = None,
        timestamp: TranscriptTimestamp | None = None,
    ) -> None:
        if sequence_number < 1:
            raise InvariantViolation(
                "sequence_number must be positive", field_name="sequence_number"
            )
        if not text.strip():
            raise InvariantViolation("transcript text must not be blank", field_name="text")
        super().__init__()
        self._sequence_number = sequence_number
        self._text = text.strip()
        self._speaker = speaker
        self._timestamp = timestamp

    @property
    def sequence_number(self) -> int:
        return self._sequence_number

    @property
    def text(self) -> str:
        return self._text

    @property
    def speaker(self) -> Speaker | None:
        return self._speaker

    @property
    def timestamp(self) -> TranscriptTimestamp | None:
        return self._timestamp


class Meeting(AggregateRoot[MeetingId]):
    def __init__(
        self,
        title: MeetingTitle,
        meeting_date: datetime,
        source: MeetingSource,
        meeting_id: MeetingId | None = None,
    ) -> None:
        super().__init__(meeting_id)
        self._title = title
        self._meeting_date = meeting_date
        self._source = source
        self._status = MeetingStatus.DRAFT
        self._segments: list[TranscriptSegment] = []

    @property
    def title(self) -> MeetingTitle:
        return self._title

    @property
    def meeting_date(self) -> datetime:
        return self._meeting_date

    @property
    def source(self) -> MeetingSource:
        return self._source

    @property
    def status(self) -> MeetingStatus:
        return self._status

    @property
    def transcript(self) -> tuple[TranscriptSegment, ...]:
        return tuple(self._segments)

    def rename(self, title: MeetingTitle) -> None:
        if self._status is MeetingStatus.ARCHIVED:
            raise InvalidStateTransition("Meeting", self._status, MeetingStatus.READY)
        self._title = title

    def begin_transcription(self) -> None:
        ensure_meeting_can_receive_transcript(self._status)
        self._status = MeetingStatus.TRANSCRIBING

    def add_transcript_segment(self, segment: TranscriptSegment) -> None:
        ensure_meeting_can_receive_transcript(self._status)
        expected = len(self._segments) + 1
        if segment.sequence_number != expected:
            raise InvariantViolation(
                f"Transcript segment sequence must be {expected}",
                field_name="sequence_number",
            )
        self._segments.append(segment)
        self._status = MeetingStatus.TRANSCRIBING

    def complete_transcription(self) -> None:
        if not self._segments:
            raise InvariantViolation("A meeting requires transcript segments before completion")
        if self._status not in (MeetingStatus.DRAFT, MeetingStatus.TRANSCRIBING):
            raise InvalidStateTransition("Meeting", self._status, MeetingStatus.READY)
        self._status = MeetingStatus.READY

    def archive(self) -> None:
        ensure_meeting_can_be_archived(self._status)
        self._status = MeetingStatus.ARCHIVED
