from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID


@dataclass(frozen=True, slots=True)
class DocumentSegmentResponse:
    id: UUID
    text: str
    content_hash: str
    page_number: int | None
    paragraph_number: int | None
    section_path: str | None


@dataclass(frozen=True, slots=True)
class DocumentVersionResponse:
    id: UUID
    version_number: int
    storage_key: str
    status: str
    processing_error: str | None
    segments: tuple[DocumentSegmentResponse, ...]


@dataclass(frozen=True, slots=True)
class DocumentResponse:
    id: UUID
    title: str
    source_filename: str
    mime_type: str
    content_hash: str
    document_type: str
    classification: str
    legal_hold: bool
    versions: tuple[DocumentVersionResponse, ...]
