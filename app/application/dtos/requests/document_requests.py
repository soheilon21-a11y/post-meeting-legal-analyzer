from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.application.exceptions.validation import ApplicationValidationError
from app.domain.document.enums import DocumentClassification
from app.domain.document.enums import DocumentType

if TYPE_CHECKING:
    from app.application.dtos.internal.security import ActorContext


@dataclass(frozen=True, slots=True)
class RegisterDocumentRequest:
    matter_id: str
    title: str
    source_filename: str
    mime_type: str
    content_hash: str
    actor: ActorContext
    document_type: DocumentType = DocumentType.OTHER
    classification: DocumentClassification = DocumentClassification.INTERNAL

    def __post_init__(self) -> None:
        for field_name, value in (
            ("matter_id", self.matter_id),
            ("title", self.title),
            ("source_filename", self.source_filename),
            ("mime_type", self.mime_type),
            ("content_hash", self.content_hash),
        ):
            if not value.strip():
                raise ApplicationValidationError(
                    f"{field_name} must not be blank", field=field_name
                )


@dataclass(frozen=True, slots=True)
class AddDocumentVersionRequest:
    document_id: str
    storage_key: str
    actor: ActorContext

    def __post_init__(self) -> None:
        if not self.storage_key.strip():
            raise ApplicationValidationError("Storage key must not be blank", field="storage_key")
