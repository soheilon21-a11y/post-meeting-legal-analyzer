from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.application.commands.base import Command
from app.domain.document.enums import DocumentClassification
from app.domain.document.enums import DocumentType

if TYPE_CHECKING:
    from uuid import UUID

    from app.application.dtos.internal.security import ActorContext
    from app.domain.shared.identifiers import DocumentId
    from app.domain.shared.identifiers import MatterId


@dataclass(frozen=True, slots=True, kw_only=True)
class RegisterDocumentCommand(Command):
    matter_id: MatterId
    title: str
    source_filename: str
    mime_type: str
    content_hash: str
    actor: ActorContext
    document_type: DocumentType = DocumentType.OTHER
    classification: DocumentClassification = DocumentClassification.INTERNAL


@dataclass(frozen=True, slots=True, kw_only=True)
class AddDocumentVersionCommand(Command):
    matter_id: MatterId
    document_id: DocumentId
    storage_key: str
    actor: ActorContext


@dataclass(frozen=True, slots=True, kw_only=True)
class ProcessDocumentVersionCommand(Command):
    matter_id: MatterId
    document_id: DocumentId
    version_id: UUID
    actor: ActorContext


@dataclass(frozen=True, slots=True, kw_only=True)
class FailDocumentProcessingCommand(Command):
    matter_id: MatterId
    document_id: DocumentId
    version_id: UUID
    error: str
    actor: ActorContext
