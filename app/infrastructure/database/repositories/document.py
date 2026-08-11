from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.document import (
    Document,
    DocumentSegment,
    DocumentType,
    DocumentVersion,
    ProcessingStatus,
)
from app.infrastructure.database.repositories.base import SQLRepository


class DocumentRepository(SQLRepository[Document]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Document)

    async def list_by_matter(
        self,
        matter_id: UUID,
        offset: int = 0,
        limit: int = 100,
        document_type: DocumentType | None = None,
    ) -> list[Document]:
        stmt = select(Document).where(Document.matter_id == matter_id)
        if document_type:
            stmt = stmt.where(Document.document_type == document_type)
        stmt = stmt.offset(offset).limit(limit).order_by(Document.updated_at.desc().nullslast())
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count_by_matter(self, matter_id: UUID) -> int:
        stmt = select(Document).where(Document.matter_id == matter_id)
        result = await self._session.execute(stmt)
        return len(list(result.scalars().all()))

    async def get_with_versions(self, document_id: UUID) -> Document | None:
        stmt = (
            select(Document)
            .where(Document.id == document_id)
            .options(selectinload(Document.versions))
        )
        result = await self._session.execute(stmt)
        return result.unique().scalar_one_or_none()

    async def get_by_hash(self, matter_id: UUID, sha256_hash: str) -> Document | None:
        stmt = select(Document).where(
            Document.matter_id == matter_id, Document.sha256_hash == sha256_hash
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def add_version(
        self,
        document_id: UUID,
        object_storage_key: str,
        page_count: int | None = None,
        uploader_id: UUID | None = None,
    ) -> DocumentVersion:
        current_count = await self._count_versions(document_id)
        version = DocumentVersion(
            document_id=document_id,
            version_number=current_count + 1,
            object_storage_key=object_storage_key,
            page_count=page_count,
            uploader_id=uploader_id,
        )
        self._session.add(version)
        await self._session.flush()
        return version

    async def get_latest_version(self, document_id: UUID) -> DocumentVersion | None:
        stmt = (
            select(DocumentVersion)
            .where(DocumentVersion.document_id == document_id)
            .order_by(DocumentVersion.version_number.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_version_status(
        self, version_id: UUID, status: ProcessingStatus, error: str | None = None
    ) -> DocumentVersion | None:
        version = await self._session.get(DocumentVersion, version_id)
        if version:
            version.processing_status = status
            version.processing_error = error
            await self._session.flush()
        return version

    async def add_segments(
        self, version_id: UUID, segments: list[DocumentSegment]
    ) -> list[DocumentSegment]:
        for segment in segments:
            segment.document_version_id = version_id
        self._session.add_all(segments)
        await self._session.flush()
        return segments

    async def get_segments_by_version(self, version_id: UUID) -> list[DocumentSegment]:
        stmt = (
            select(DocumentSegment)
            .where(DocumentSegment.document_version_id == version_id)
            .order_by(DocumentSegment.page_number, DocumentSegment.paragraph_number)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def _count_versions(self, document_id: UUID) -> int:
        stmt = select(DocumentVersion).where(DocumentVersion.document_id == document_id)
        result = await self._session.execute(stmt)
        return len(list(result.scalars().all()))
