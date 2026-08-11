from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Protocol

from app.application.dtos.responses.document_responses import DocumentResponse
from app.application.dtos.responses.document_responses import DocumentSegmentResponse
from app.application.dtos.responses.document_responses import DocumentVersionResponse

if TYPE_CHECKING:
    from app.domain.document.entities import Document
    from app.domain.document.entities import DocumentSegment
    from app.domain.document.entities import DocumentVersion


class DocumentMapper(Protocol):
    def to_response(self, document: Document) -> DocumentResponse: ...


class DefaultDocumentMapper:
    def to_response(self, document: Document) -> DocumentResponse:
        return DocumentResponse(
            id=document.id,
            title=document.title,
            source_filename=document.source_filename.value,
            mime_type=document.mime_type.value,
            content_hash=document.content_hash.value,
            document_type=document.document_type.value,
            classification=document.classification.value,
            legal_hold=document.legal_hold,
            versions=tuple(self._version_response(version) for version in document.versions),
        )

    def _version_response(self, version: DocumentVersion) -> DocumentVersionResponse:
        return DocumentVersionResponse(
            id=version.id,
            version_number=version.version_number,
            storage_key=version.storage_key.value,
            status=version.status.value,
            processing_error=version.processing_error,
            segments=tuple(self._segment_response(segment) for segment in version.segments),
        )

    @staticmethod
    def _segment_response(segment: DocumentSegment) -> DocumentSegmentResponse:
        return DocumentSegmentResponse(
            id=segment.id,
            text=segment.text,
            content_hash=segment.content_hash.value,
            page_number=segment.page_number,
            paragraph_number=None,
            section_path=segment.section_path.value if segment.section_path else None,
        )
