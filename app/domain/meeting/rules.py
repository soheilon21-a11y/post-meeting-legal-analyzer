from app.domain.exceptions.lifecycle import InvalidStateTransition
from app.domain.meeting.enums import MeetingStatus


def ensure_meeting_can_receive_transcript(status: MeetingStatus) -> None:
    if status not in (MeetingStatus.DRAFT, MeetingStatus.TRANSCRIBING):
        raise InvalidStateTransition("Meeting", status, MeetingStatus.TRANSCRIBING)


def ensure_meeting_can_be_archived(status: MeetingStatus) -> None:
    if status is not MeetingStatus.READY:
        raise InvalidStateTransition("Meeting", status, MeetingStatus.ARCHIVED)
