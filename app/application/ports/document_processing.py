from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Protocol

if TYPE_CHECKING:
    from app.application.dtos.internal.document_processing import DocumentProcessingInput
    from app.application.dtos.internal.document_processing import DocumentProcessingResult


class DocumentProcessingPort(Protocol):
    async def process(self, request: DocumentProcessingInput) -> DocumentProcessingResult:
        """Extract and segment a document through an outer processing adapter."""
