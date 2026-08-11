from __future__ import annotations

from typing import TYPE_CHECKING

from app.application.authorization import ApplicationAuthorizationService
from app.application.authorization import MatterAction
from app.application.commands.meeting_commands import AddTranscriptSegmentCommand
from app.application.commands.meeting_commands import ArchiveMeetingCommand
from app.application.commands.meeting_commands import BeginTranscriptionCommand
from app.application.commands.meeting_commands import CompleteTranscriptionCommand
from app.application.commands.meeting_commands import CreateMeetingCommand
from app.application.lookup import ResourceLookupService
from app.application.mappers.meeting import DefaultMeetingMapper
from app.domain.meeting.entities import TranscriptSegment
from app.domain.meeting.value_objects import MeetingTitle
from app.domain.meeting.value_objects import Speaker
from app.domain.meeting.value_objects import TranscriptTimestamp

if TYPE_CHECKING:
    from collections.abc import Callable

    from app.application.dtos.responses.meeting_responses import MeetingResponse
    from app.application.mappers.meeting import MeetingMapper
    from app.application.ports.meeting_uow import MeetingUnitOfWork
    from app.application.queries.meeting_queries import GetMeetingQuery
    from app.application.queries.meeting_queries import GetMeetingTranscriptQuery
    from app.domain.meeting.entities import Meeting


class MeetingCommandHandler:
    def __init__(
        self,
        uow_factory: Callable[[], MeetingUnitOfWork],
        mapper: MeetingMapper | None = None,
        authorization: ApplicationAuthorizationService | None = None,
        lookup: ResourceLookupService | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._mapper = mapper or DefaultMeetingMapper()
        self._authorization = authorization or ApplicationAuthorizationService()
        self._lookup = lookup or ResourceLookupService()

    async def handle(
        self,
        command: (
            CreateMeetingCommand
            | AddTranscriptSegmentCommand
            | BeginTranscriptionCommand
            | CompleteTranscriptionCommand
            | ArchiveMeetingCommand
        ),
    ) -> MeetingResponse:
        async with self._uow_factory() as uow:
            matter = await self._lookup.matter(uow.matters, command.matter_id)
            self._authorization.require_matter_access(command.actor, matter, MatterAction.EDIT)
            if isinstance(command, CreateMeetingCommand):
                meeting = self._create(command)
            else:
                meeting = await self._lookup.meeting(
                    uow.meetings, command.matter_id, command.meeting_id
                )
                self._mutate(meeting, command)
            await uow.meetings.save(meeting)
            await uow.commit()
            return self._mapper.to_response(meeting)

    @staticmethod
    def _create(command: CreateMeetingCommand) -> Meeting:
        from app.domain.meeting.entities import Meeting

        return Meeting(
            title=MeetingTitle(command.title),
            meeting_date=command.meeting_date,
            source=command.source,
        )

    @staticmethod
    def _mutate(meeting: object, command: object) -> None:
        from app.domain.meeting.entities import Meeting

        if not isinstance(meeting, Meeting):
            raise TypeError("Expected Meeting aggregate")
        if isinstance(command, AddTranscriptSegmentCommand):
            timestamp = (
                TranscriptTimestamp(command.start_seconds, command.end_seconds)
                if command.start_seconds is not None and command.end_seconds is not None
                else None
            )
            meeting.add_transcript_segment(
                TranscriptSegment(
                    sequence_number=command.sequence_number,
                    text=command.text,
                    speaker=Speaker(command.speaker) if command.speaker else None,
                    timestamp=timestamp,
                )
            )
        elif isinstance(command, BeginTranscriptionCommand):
            meeting.begin_transcription()
        elif isinstance(command, CompleteTranscriptionCommand):
            meeting.complete_transcription()
        else:
            meeting.archive()


class MeetingQueryHandler:
    def __init__(
        self,
        uow_factory: Callable[[], MeetingUnitOfWork],
        mapper: MeetingMapper | None = None,
        authorization: ApplicationAuthorizationService | None = None,
        lookup: ResourceLookupService | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._mapper = mapper or DefaultMeetingMapper()
        self._authorization = authorization or ApplicationAuthorizationService()
        self._lookup = lookup or ResourceLookupService()

    async def handle(self, query: GetMeetingQuery | GetMeetingTranscriptQuery) -> MeetingResponse:
        async with self._uow_factory() as uow:
            matter = await self._lookup.matter(uow.matters, query.matter_id)
            self._authorization.require_matter_access(query.actor, matter, MatterAction.READ)
            meeting = await self._lookup.meeting(uow.meetings, query.matter_id, query.meeting_id)
            return self._mapper.to_response(meeting)
