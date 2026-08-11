from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Protocol

if TYPE_CHECKING:
    from app.domain.document.value_objects import MimeType
    from app.domain.document.value_objects import StorageKey


class DocumentStoragePort(Protocol):
    async def store(self, content: bytes, storage_key: StorageKey, mime_type: MimeType) -> None:
        """Store immutable source bytes under a validated key."""

    async def read(self, storage_key: StorageKey) -> bytes:
        """Read source bytes for local processing."""

    async def delete(self, storage_key: StorageKey) -> None:
        """Delete source bytes when retention policy permits it."""
