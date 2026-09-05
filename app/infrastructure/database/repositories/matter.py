from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.models.matter import Matter
from app.db.models.matter import MatterMember
from app.db.models.matter import MatterMemberRole
from app.infrastructure.database.repositories.base import SQLRepository

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession


class MatterRepository(SQLRepository[Matter]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Matter)

    async def list_by_organization(
        self,
        org_id: UUID,
        offset: int = 0,
        limit: int = 100,
    ) -> list[Matter]:
        stmt = (
            select(Matter)
            .where(Matter.organization_id == org_id)
            .offset(offset)
            .limit(limit)
            .order_by(Matter.updated_at.desc().nullslast())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count_by_organization(self, org_id: UUID) -> int:
        stmt = select(Matter).where(Matter.organization_id == org_id)
        result = await self._session.execute(stmt)
        return len(list(result.scalars().all()))

    async def get_with_members(self, matter_id: UUID) -> Matter | None:
        stmt = (
            select(Matter)
            .where(Matter.id == matter_id)
            .options(selectinload(Matter.members).selectinload(MatterMember.user))
        )
        result = await self._session.execute(stmt)
        return result.unique().scalar_one_or_none()

    async def list_by_user(
        self,
        user_id: UUID,
        offset: int = 0,
        limit: int = 100,
    ) -> list[Matter]:
        stmt = (
            select(Matter)
            .join(MatterMember, MatterMember.matter_id == Matter.id)
            .where(MatterMember.user_id == user_id)
            .offset(offset)
            .limit(limit)
            .order_by(Matter.updated_at.desc().nullslast())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def add_member(
        self,
        matter_id: UUID,
        user_id: UUID,
        role: MatterMemberRole = MatterMemberRole.VIEWER,
    ) -> MatterMember:
        member = MatterMember(matter_id=matter_id, user_id=user_id, role=role)
        self._session.add(member)
        await self._session.flush()
        return member

    async def remove_member(self, matter_id: UUID, user_id: UUID) -> bool:
        stmt = select(MatterMember).where(
            MatterMember.matter_id == matter_id, MatterMember.user_id == user_id
        )
        result = await self._session.execute(stmt)
        member = result.scalar_one_or_none()
        if member:
            await self._session.delete(member)
            await self._session.flush()
            return True
        return False

    async def get_user_role(self, matter_id: UUID, user_id: UUID) -> MatterMemberRole | None:
        stmt = select(MatterMember).where(
            MatterMember.matter_id == matter_id, MatterMember.user_id == user_id
        )
        result = await self._session.execute(stmt)
        member = result.scalar_one_or_none()
        return member.role if member else None
