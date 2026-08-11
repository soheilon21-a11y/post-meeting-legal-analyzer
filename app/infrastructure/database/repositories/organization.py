from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.organization import Organization
from app.infrastructure.database.repositories.base import SQLRepository


class OrganizationRepository(SQLRepository[Organization]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Organization)

    async def get_by_name(self, name: str) -> Organization | None:
        stmt = select(Organization).where(Organization.name == name)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_with_users(self, id: UUID) -> Organization | None:
        stmt = select(Organization).where(Organization.id == id)
        result = await self._session.execute(stmt)
        return result.unique().scalar_one_or_none()

    async def get_with_matters(self, id: UUID) -> Organization | None:
        stmt = select(Organization).where(Organization.id == id)
        result = await self._session.execute(stmt)
        return result.unique().scalar_one_or_none()
