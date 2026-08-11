from __future__ import annotations

from typing import TYPE_CHECKING

from app.application.authorization import ApplicationAuthorizationService
from app.application.authorization import MatterAction
from app.application.commands.document_commands import AddDocumentVersionCommand
from app.application.commands.document_commands import FailDocumentProcessingCommand
from app.application.commands.document_commands import ProcessDocumentVersionCommand
from app.application.commands.document_commands import RegisterDocumentCommand
from app.application.dtos.internal.document_processing import DocumentProcessingInput
from app.application.exceptions.not_found import ResourceNotFound
from app.application.lookup import ResourceLookupService
from app.application.mappers.document import DefaultDocumentMapper
from app.domain.document.entities import DocumentSegment
from app.domain.document.value_objects import ContentHash
from app.domain.document.value_objects import FileName
from app.domain.document.value_objects import MimeType
from app.domain.document.value_objects import SectionPath
from app.domain.document.value_objects import StorageKey

if TYPE_CHECKING:
    from collections.abc import Callable
    from uuid import UUID

    from app.application.dtos.responses.document_responses import DocumentResponse
    from app.application.mappers.document import DocumentMapper
    from app.application.ports.document_processing import DocumentProcessingPort
    from app.application.ports.document_uow import DocumentUnitOfWork
    from app.application.queries.document_queries import GetDocumentQuery
    from app.application.queries.document_queries import GetDocumentVersionsQuery
    from app.domain.document.entities import Document
    from app.domain.document.entities import DocumentVersion


class DocumentCommandHandler:
    def __init__(
        self,
        uow_factory: Callable[[], DocumentUnitOfWork],
        processing_port: DocumentProcessingPort | None = None,
        mapper: DocumentMapper | None = None,
        authorization: ApplicationAuthorizationService | None = None,
        lookup: ResourceLookupService | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._processing_port = processing_port
        self._mapper = mapper or DefaultDocumentMapper()
        self._authorization = authorization or ApplicationAuthorizationService()
        self._lookup = lookup or ResourceLookupService()

    async def handle(
        self,
        command: (
            RegisterDocumentCommand
            | AddDocumentVersionCommand
            | ProcessDocumentVersionCommand
            | FailDocumentProcessingCommand
        ),
    ) -> DocumentResponse:
        async with self._uow_factory() as uow:
            matter = await self._lookup.matter(uow.matters, command.matter_id)
            self._authorization.require_matter_access(command.actor, matter, MatterAction.EDIT)
            if isinstance(command, RegisterDocumentCommand):
                document = self._register(command)
            else:
                document = await self._lookup.document(
                    uow.documents, command.matter_id, command.document_id
                )
                if isinstance(command, AddDocumentVersionCommand):
                    document.add_version(StorageKey(command.storage_key))
                elif isinstance(command, ProcessDocumentVersionCommand):
                    await self._process(document, command.version_id)
                else:
                    self._fail(document, command.version_id, command.error)
            await uow.documents.save(document)
            await uow.commit()
            return self._mapper.to_response(document)

    @staticmethod
    def _register(command: RegisterDocumentCommand) -> Document:
        from app.domain.document.entities import Document

        return Document(
            title=command.title,
            source_filename=FileName(command.source_filename),
            mime_type=MimeType(command.mime_type),
            content_hash=ContentHash(command.content_hash),
            document_type=command.document_type,
            classification=command.classification,
        )

    async def _process(self, document: object, version_id: UUID) -> None:
        from app.domain.document.entities import Document

        if not isinstance(document, Document):
            raise TypeError("Expected Document aggregate")
        version = self._version(document, version_id)
        if self._processing_port is None:
            raise ValueError("Document processing port is required for processing")
        version.start_processing()
        result = await self._processing_port.process(
            DocumentProcessingInput(
                document_id=document.id,
                version_id=version.id,
                storage_key=version.storage_key.value,
                mime_type=document.mime_type.value,
            )
        )
        for segment in result.segments:
            version.add_segment(
                DocumentSegment(
                    text=segment.text,
                    content_hash=ContentHash(segment.content_hash),
                    page_number=segment.page_number,
                    paragraph_number=segment.paragraph_number,
                    section_path=(
                        SectionPath(segment.section_path) if segment.section_path else None
                    ),
                )
            )
        version.complete_processing()

    @staticmethod
    def _fail(document: object, version_id: UUID, error: str) -> None:
        from app.domain.document.entities import Document

        if not isinstance(document, Document):
            raise TypeError("Expected Document aggregate")
        DocumentCommandHandler._version(document, version_id).fail_processing(error)

    @staticmethod
    def _version(document: object, version_id: UUID) -> DocumentVersion:
        from app.domain.document.entities import Document

        if not isinstance(document, Document):
            raise TypeError("Expected Document aggregate")
        version = next((item for item in document.versions if item.id == version_id), None)
        if version is None:
            raise ResourceNotFound("DocumentVersion", str(version_id))
        return version


class DocumentQueryHandler:
    def __init__(
        self,
        uow_factory: Callable[[], DocumentUnitOfWork],
        mapper: DocumentMapper | None = None,
        authorization: ApplicationAuthorizationService | None = None,
        lookup: ResourceLookupService | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._mapper = mapper or DefaultDocumentMapper()
        self._authorization = authorization or ApplicationAuthorizationService()
        self._lookup = lookup or ResourceLookupService()

    async def handle(self, query: GetDocumentQuery | GetDocumentVersionsQuery) -> DocumentResponse:
        async with self._uow_factory() as uow:
            matter = await self._lookup.matter(uow.matters, query.matter_id)
            self._authorization.require_matter_access(query.actor, matter, MatterAction.READ)
            document = await self._lookup.document(
                uow.documents, query.matter_id, query.document_id
            )
            return self._mapper.to_response(document)
