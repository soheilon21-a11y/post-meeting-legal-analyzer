from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Protocol

from app.application.dtos.responses.meeting_responses import MeetingResponse
from app.application.dtos.responses.meeting_responses import TranscriptSegmentResponse

if TYPE_CHECKING:
    from app.domain.meeting.entities import Meeting


class MeetingMapper(Protocol):
    def to_response(self, meeting: Meeting) -> MeetingResponse: ...

    def transcript_response(self, meeting: Meeting) -> tuple[TranscriptSegmentResponse, ...]: ...


class DefaultMeetingMapper:
    def to_response(self, meeting: Meeting) -> MeetingResponse:
        return MeetingResponse(
            id=meeting.id,
            title=meeting.title.value,
            meeting_date=meeting.meeting_date,
            source=meeting.source.value,
            status=meeting.status.value,
            transcript=self.transcript_response(meeting),
        )

    def transcript_response(self, meeting: Meeting) -> tuple[TranscriptSegmentResponse, ...]:
        return tuple(
            TranscriptSegmentResponse(
                id=segment.id,
                sequence_number=segment.sequence_number,
                text=segment.text,
                speaker=segment.speaker.value if segment.speaker else None,
                start_seconds=segment.timestamp.start_seconds if segment.timestamp else None,
                end_seconds=segment.timestamp.end_seconds if segment.timestamp else None,
            )
            for segment in meeting.transcript
        )
