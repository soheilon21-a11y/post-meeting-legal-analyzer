from __future__ import annotations

from datetime import UTC
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from app.application.commands.document_commands import AddDocumentVersionCommand
from app.application.commands.document_commands import FailDocumentProcessingCommand
from app.application.commands.document_commands import ProcessDocumentVersionCommand
from app.application.commands.document_commands import RegisterDocumentCommand
from app.application.commands.meeting_commands import AddTranscriptSegmentCommand
from app.application.commands.meeting_commands import CompleteTranscriptionCommand
from app.application.commands.meeting_commands import CreateMeetingCommand
from app.application.dtos.internal.document_processing import DocumentProcessingInput
from app.application.dtos.internal.document_processing import DocumentProcessingResult
from app.application.dtos.internal.document_processing import ProcessedDocumentSegment
from app.application.dtos.internal.security import ActorContext
from app.application.exceptions import AuthorizationError
from app.application.handlers.document_handlers import DocumentCommandHandler
from app.application.handlers.document_handlers import DocumentQueryHandler
from app.application.handlers.meeting_handlers import MeetingCommandHandler
from app.application.handlers.meeting_handlers import MeetingQueryHandler
from app.application.ports.document_processing import DocumentProcessingPort
from app.application.queries.document_queries import GetDocumentQuery
from app.application.queries.meeting_queries import GetMeetingQuery
from app.domain.document.enums import DocumentType
from app.domain.matter.entities import Matter
from app.domain.matter.enums import MatterMemberRole
from app.domain.matter.value_objects import MatterName
from app.domain.meeting.enums import MeetingSource
from app.domain.shared.identifiers import DocumentId
from app.domain.shared.identifiers import MatterId
from app.domain.shared.identifiers import MeetingId
from app.domain.shared.identifiers import OrganizationId
from app.domain.shared.identifiers import UserId

if TYPE_CHECKING:
    from app.domain.document.entities import Document
    from app.domain.meeting.entities import Meeting


class InMemoryMatterRepository:
    def __init__(self, matter: Matter) -> None:
        self.matter = matter

    async def get(self, matter_id: MatterId) -> Matter | None:
        return self.matter if matter_id == self.matter.id else None

    async def save(self, matter: Matter) -> None:
        self.matter = matter


class InMemoryMeetingRepository:
    def __init__(self) -> None:
        self.items: dict[MeetingId, Meeting] = {}

    async def get(self, meeting_id: MeetingId) -> Meeting | None:
        return self.items.get(meeting_id)

    async def save(self, meeting: Meeting) -> None:
        self.items[meeting.id] = meeting

    async def get_for_matter(self, matter_id: MatterId, meeting_id: MeetingId) -> Meeting | None:
        return self.items.get(meeting_id)


class InMemoryDocumentRepository:
    def __init__(self) -> None:
        self.items: dict[DocumentId, Document] = {}

    async def get(self, document_id: DocumentId) -> Document | None:
        return self.items.get(document_id)

    async def save(self, document: Document) -> None:
        self.items[document.id] = document

    async def get_for_matter(self, matter_id: MatterId, document_id: DocumentId) -> Document | None:
        return self.items.get(document_id)


class MeetingUnitOfWorkFake:
    def __init__(self, matter: Matter) -> None:
        self.matters = InMemoryMatterRepository(matter)
        self.meetings = InMemoryMeetingRepository()
        self.commits = 0

    async def __aenter__(self) -> MeetingUnitOfWorkFake:
        return self

    async def __aexit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        return None

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        return None


class DocumentUnitOfWorkFake:
    def __init__(self, matter: Matter) -> None:
        self.matters = InMemoryMatterRepository(matter)
        self.documents = InMemoryDocumentRepository()
        self.commits = 0

    async def __aenter__(self) -> DocumentUnitOfWorkFake:
        return self

    async def __aexit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        return None

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        return None


class FakeDocumentProcessor(DocumentProcessingPort):
    async def process(self, request: DocumentProcessingInput) -> DocumentProcessingResult:
        return DocumentProcessingResult(
            segments=(
                ProcessedDocumentSegment(
                    text="A processed clause.",
                    content_hash="b" * 64,
                    page_number=1,
                    section_path="1. Scope",
                ),
            )
        )


def _matter_with_owner() -> tuple[Matter, ActorContext]:
    matter = Matter(MatterName("Matter"))
    actor = ActorContext(user_id=UserId(uuid4()), organization_id=OrganizationId(uuid4()))
    matter.add_member(actor.user_id, MatterMemberRole.OWNER)
    return matter, actor


@pytest.mark.anyio
async def test_meeting_workflow_creates_transcript_and_completes() -> None:
    matter, actor = _matter_with_owner()
    uow = MeetingUnitOfWorkFake(matter)
    handler = MeetingCommandHandler(lambda: uow)

    created = await handler.handle(
        CreateMeetingCommand(
            matter_id=matter.id,
            title="Client meeting",
            meeting_date=datetime.now(UTC),
            source=MeetingSource.TEXT,
            actor=actor,
        )
    )
    await handler.handle(
        AddTranscriptSegmentCommand(
            matter_id=matter.id,
            meeting_id=MeetingId(created.id),
            sequence_number=1,
            text="We agree to proceed.",
            actor=actor,
        )
    )
    completed = await handler.handle(
        CompleteTranscriptionCommand(
            matter_id=matter.id,
            meeting_id=MeetingId(created.id),
            actor=actor,
        )
    )

    queried = await MeetingQueryHandler(lambda: uow).handle(
        GetMeetingQuery(
            matter_id=matter.id,
            meeting_id=MeetingId(created.id),
            actor=actor,
        )
    )
    assert completed.status == "ready"
    assert queried.transcript[0].text == "We agree to proceed."
    assert uow.commits == 3


@pytest.mark.anyio
async def test_meeting_requires_matter_access() -> None:
    matter, owner = _matter_with_owner()
    outsider = ActorContext(user_id=UserId(uuid4()), organization_id=owner.organization_id)
    uow = MeetingUnitOfWorkFake(matter)

    with pytest.raises(AuthorizationError):
        await MeetingCommandHandler(lambda: uow).handle(
            CreateMeetingCommand(
                matter_id=matter.id,
                title="Unauthorized meeting",
                meeting_date=datetime.now(UTC),
                source=MeetingSource.TEXT,
                actor=outsider,
            )
        )


@pytest.mark.anyio
async def test_document_workflow_processes_version_and_maps_segments() -> None:
    matter, actor = _matter_with_owner()
    uow = DocumentUnitOfWorkFake(matter)
    handler = DocumentCommandHandler(lambda: uow, processing_port=FakeDocumentProcessor())

    created = await handler.handle(
        RegisterDocumentCommand(
            matter_id=matter.id,
            title="Agreement",
            source_filename="agreement.pdf",
            mime_type="application/pdf",
            content_hash="a" * 64,
            actor=actor,
            document_type=DocumentType.CONTRACT,
        )
    )
    versioned = await handler.handle(
        AddDocumentVersionCommand(
            matter_id=matter.id,
            document_id=DocumentId(created.id),
            storage_key="matter/agreement-v1.pdf",
            actor=actor,
        )
    )
    version_id = DocumentId(versioned.versions[0].id)
    processed = await handler.handle(
        ProcessDocumentVersionCommand(
            matter_id=matter.id,
            document_id=DocumentId(created.id),
            version_id=version_id,
            actor=actor,
        )
    )
    queried = await DocumentQueryHandler(lambda: uow).handle(
        GetDocumentQuery(
            matter_id=matter.id,
            document_id=DocumentId(created.id),
            actor=actor,
        )
    )

    assert processed.versions[0].status == "completed"
    assert queried.versions[0].segments[0].section_path == "1. Scope"


@pytest.mark.anyio
async def test_document_processing_failure_is_recorded() -> None:
    matter, actor = _matter_with_owner()
    uow = DocumentUnitOfWorkFake(matter)
    handler = DocumentCommandHandler(lambda: uow)
    created = await handler.handle(
        RegisterDocumentCommand(
            matter_id=matter.id,
            title="Policy",
            source_filename="policy.pdf",
            mime_type="application/pdf",
            content_hash="a" * 64,
            actor=actor,
        )
    )
    versioned = await handler.handle(
        AddDocumentVersionCommand(
            matter_id=matter.id,
            document_id=DocumentId(created.id),
            storage_key="matter/policy-v1.pdf",
            actor=actor,
        )
    )
    failed = await handler.handle(
        FailDocumentProcessingCommand(
            matter_id=matter.id,
            document_id=DocumentId(created.id),
            version_id=DocumentId(versioned.versions[0].id),
            error="Unsupported layout",
            actor=actor,
        )
    )

    assert failed.versions[0].status == "failed"
    assert failed.versions[0].processing_error == "Unsupported layout"
