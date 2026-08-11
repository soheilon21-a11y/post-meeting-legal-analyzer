from __future__ import annotations

from typing import TYPE_CHECKING

from app.domain.document.enums import DocumentClassification
from app.domain.document.enums import DocumentType
from app.domain.document.enums import ProcessingStatus
from app.domain.document.rules import ensure_document_can_change
from app.domain.document.rules import ensure_processing_transition
from app.domain.exceptions.invariant import InvariantViolation
from app.domain.shared.aggregate_root import AggregateRoot
from app.domain.shared.entity import Entity
from app.domain.shared.identifiers import DocumentId

if TYPE_CHECKING:
    from app.domain.document.value_objects import ContentHash
    from app.domain.document.value_objects import FileName
    from app.domain.document.value_objects import MimeType
    from app.domain.document.value_objects import SectionPath
    from app.domain.document.value_objects import StorageKey


class DocumentSegment(Entity[DocumentId]):
    def __init__(
        self,
        text: str,
        content_hash: ContentHash,
        page_number: int | None = None,
        paragraph_number: int | None = None,
        section_path: SectionPath | None = None,
    ) -> None:
        if not text.strip():
            raise InvariantViolation("document segment text must not be blank", field_name="text")
        if page_number is not None and page_number < 1:
            raise InvariantViolation("page_number must be positive", field_name="page_number")
        super().__init__()
        self._text = text.strip()
        self._content_hash = content_hash
        self._page_number = page_number
        self._paragraph_number = paragraph_number
        self._section_path = section_path

    @property
    def text(self) -> str:
        return self._text

    @property
    def content_hash(self) -> ContentHash:
        return self._content_hash

    @property
    def page_number(self) -> int | None:
        return self._page_number

    @property
    def section_path(self) -> SectionPath | None:
        return self._section_path

    @property
    def paragraph_number(self) -> int | None:
        return self._paragraph_number


class DocumentVersion(Entity[DocumentId]):
    def __init__(self, version_number: int, storage_key: StorageKey) -> None:
        if version_number < 1:
            raise InvariantViolation("version_number must be positive", field_name="version_number")
        super().__init__()
        self._version_number = version_number
        self._storage_key = storage_key
        self._status = ProcessingStatus.PENDING
        self._segments: list[DocumentSegment] = []
        self._processing_error: str | None = None

    @property
    def version_number(self) -> int:
        return self._version_number

    @property
    def storage_key(self) -> StorageKey:
        return self._storage_key

    @property
    def status(self) -> ProcessingStatus:
        return self._status

    @property
    def segments(self) -> tuple[DocumentSegment, ...]:
        return tuple(self._segments)

    @property
    def processing_error(self) -> str | None:
        return self._processing_error

    def add_segment(self, segment: DocumentSegment) -> None:
        if self._status is ProcessingStatus.COMPLETED:
            raise ValueError("Completed document versions cannot receive segments")
        self._segments.append(segment)

    def start_processing(self) -> None:
        ensure_processing_transition(self._status, ProcessingStatus.PROCESSING)
        self._status = ProcessingStatus.PROCESSING
        self._processing_error = None

    def complete_processing(self) -> None:
        if not self._segments:
            raise InvariantViolation("A document version requires segments before completion")
        ensure_processing_transition(self._status, ProcessingStatus.COMPLETED)
        self._status = ProcessingStatus.COMPLETED

    def fail_processing(self, error: str) -> None:
        if not error.strip():
            raise InvariantViolation("processing error must not be blank", field_name="error")
        ensure_processing_transition(self._status, ProcessingStatus.FAILED)
        self._status = ProcessingStatus.FAILED
        self._processing_error = error.strip()


class Document(AggregateRoot[DocumentId]):
    def __init__(
        self,
        title: str,
        source_filename: FileName,
        mime_type: MimeType,
        content_hash: ContentHash,
        document_type: DocumentType = DocumentType.OTHER,
        classification: DocumentClassification = DocumentClassification.INTERNAL,
        document_id: DocumentId | None = None,
    ) -> None:
        if not title.strip():
            raise InvariantViolation("document title must not be blank", field_name="title")
        super().__init__(document_id)
        self._title = title.strip()
        self._source_filename = source_filename
        self._mime_type = mime_type
        self._content_hash = content_hash
        self._document_type = document_type
        self._classification = classification
        self._legal_hold = False
        self._versions: list[DocumentVersion] = []

    @property
    def title(self) -> str:
        return self._title

    @property
    def source_filename(self) -> FileName:
        return self._source_filename

    @property
    def mime_type(self) -> MimeType:
        return self._mime_type

    @property
    def content_hash(self) -> ContentHash:
        return self._content_hash

    @property
    def document_type(self) -> DocumentType:
        return self._document_type

    @property
    def classification(self) -> DocumentClassification:
        return self._classification

    @property
    def legal_hold(self) -> bool:
        return self._legal_hold

    @property
    def versions(self) -> tuple[DocumentVersion, ...]:
        return tuple(self._versions)

    def rename(self, title: str) -> None:
        ensure_document_can_change(self._legal_hold)
        if not title.strip():
            raise InvariantViolation("document title must not be blank", field_name="title")
        self._title = title.strip()

    def add_version(self, storage_key: StorageKey) -> DocumentVersion:
        ensure_document_can_change(self._legal_hold)
        version = DocumentVersion(len(self._versions) + 1, storage_key)
        self._versions.append(version)
        return version

    def apply_legal_hold(self) -> None:
        self._legal_hold = True

    def release_legal_hold(self) -> None:
        self._legal_hold = False
