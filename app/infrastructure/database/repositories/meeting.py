from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.meeting import Meeting, TranscriptSegment
from app.infrastructure.database.repositories.base import SQLRepository


class MeetingRepository(SQLRepository[Meeting]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Meeting)

    async def list_by_matter(
        self,
        matter_id: UUID,
        offset: int = 0,
        limit: int = 100,
    ) -> list[Meeting]:
        stmt = (
            select(Meeting)
            .where(Meeting.matter_id == matter_id)
            .offset(offset)
            .limit(limit)
            .order_by(Meeting.meeting_date.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count_by_matter(self, matter_id: UUID) -> int:
        stmt = select(Meeting).where(Meeting.matter_id == matter_id)
        result = await self._session.execute(stmt)
        return len(list(result.scalars().all()))

    async def get_with_segments(self, meeting_id: UUID) -> Meeting | None:
        stmt = (
            select(Meeting)
            .where(Meeting.id == meeting_id)
            .options(
                selectinload(Meeting.transcript_segments).order_by(
                    TranscriptSegment.sequence_number
                )
            )
        )
        result = await self._session.execute(stmt)
        return result.unique().scalar_one_or_none()

    async def add_segment(
        self,
        meeting_id: UUID,
        speaker: str | None,
        text: str,
        sequence_number: int,
        start_time: float | None = None,
        end_time: float | None = None,
    ) -> TranscriptSegment:
        segment = TranscriptSegment(
            meeting_id=meeting_id,
            speaker=speaker,
            text=text,
            sequence_number=sequence_number,
            start_time=start_time,
            end_time=end_time,
        )
        self._session.add(segment)
        await self._session.flush()
        return segment

    async def update_segment(self, segment: TranscriptSegment) -> TranscriptSegment:
        await self._session.merge(segment)
        await self._session.flush()
        return segment

    async def delete_segment(self, segment_id: UUID) -> bool:
        segment = await self._session.get(TranscriptSegment, segment_id)
        if segment:
            await self._session.delete(segment)
            await self._session.flush()
            return True
        return False
