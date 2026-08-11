from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID


@dataclass(frozen=True, slots=True)
class DocumentProcessingInput:
    document_id: UUID
    version_id: UUID
    storage_key: str
    mime_type: str


@dataclass(frozen=True, slots=True)
class ProcessedDocumentSegment:
    text: str
    content_hash: str
    page_number: int | None = None
    paragraph_number: int | None = None
    section_path: str | None = None


@dataclass(frozen=True, slots=True)
class DocumentProcessingResult:
    segments: tuple[ProcessedDocumentSegment, ...]
