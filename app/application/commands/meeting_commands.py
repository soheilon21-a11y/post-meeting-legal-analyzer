from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.application.commands.base import Command

if TYPE_CHECKING:
    from datetime import datetime

    from app.application.dtos.internal.security import ActorContext
    from app.domain.meeting.enums import MeetingSource
    from app.domain.shared.identifiers import MatterId
    from app.domain.shared.identifiers import MeetingId


@dataclass(frozen=True, slots=True, kw_only=True)
class CreateMeetingCommand(Command):
    matter_id: MatterId
    title: str
    meeting_date: datetime
    source: MeetingSource
    actor: ActorContext


@dataclass(frozen=True, slots=True, kw_only=True)
class AddTranscriptSegmentCommand(Command):
    matter_id: MatterId
    meeting_id: MeetingId
    sequence_number: int
    text: str
    actor: ActorContext
    speaker: str | None = None
    start_seconds: float | None = None
    end_seconds: float | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class BeginTranscriptionCommand(Command):
    matter_id: MatterId
    meeting_id: MeetingId
    actor: ActorContext


@dataclass(frozen=True, slots=True, kw_only=True)
class CompleteTranscriptionCommand(Command):
    matter_id: MatterId
    meeting_id: MeetingId
    actor: ActorContext


@dataclass(frozen=True, slots=True, kw_only=True)
class ArchiveMeetingCommand(Command):
    matter_id: MatterId
    meeting_id: MeetingId
    actor: ActorContext
