from __future__ import annotations

from abc import ABC
from abc import abstractmethod
from typing import TYPE_CHECKING
from typing import Generic
from typing import TypeVar

from sqlalchemy import delete
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy import update
from sqlalchemy.orm import DeclarativeBase

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T", bound=DeclarativeBase)


class AbstractRepository(ABC, Generic[T]):
    @abstractmethod
    async def get(self, id: UUID) -> T | None:
        raise NotImplementedError

    @abstractmethod
    async def list(
        self,
        offset: int = 0,
        limit: int = 100,
        order_by: str | None = None,
        descending: bool = False,
    ) -> list[T]:
        raise NotImplementedError

    @abstractmethod
    async def count(self) -> int:
        raise NotImplementedError

    @abstractmethod
    async def add(self, entity: T) -> T:
        raise NotImplementedError

    @abstractmethod
    async def update(self, entity: T) -> T:
        raise NotImplementedError

    @abstractmethod
    async def delete(self, id: UUID, soft: bool = True) -> bool:
        raise NotImplementedError


class SQLRepository(AbstractRepository[T]):
    def __init__(self, session: AsyncSession, model: type[T]) -> None:
        self._session = session
        self._model = model

    async def get(self, id: UUID) -> T | None:
        stmt = select(self._model).where(self._model.id == id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list(
        self,
        offset: int = 0,
        limit: int = 100,
        order_by: str | None = None,
        descending: bool = False,
    ) -> list[T]:
        stmt = select(self._model)
        if order_by:
            col = getattr(self._model, order_by, None)
            if col is not None:
                stmt = stmt.order_by(col.desc() if descending else col.asc())
        stmt = stmt.offset(offset).limit(limit)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count(self) -> int:
        stmt = select(func.count()).select_from(self._model)
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def add(self, entity: T) -> T:
        self._session.add(entity)
        await self._session.flush()
        return entity

    async def update(self, entity: T) -> T:
        await self._session.merge(entity)
        await self._session.flush()
        return entity

    async def delete(self, id: UUID, soft: bool = True) -> bool:
        if soft and hasattr(self._model, "deleted_at"):
            from datetime import UTC
            from datetime import datetime

            stmt = (
                update(self._model)
                .where(self._model.id == id)
                .values(deleted_at=datetime.now(UTC))
            )
            result = await self._session.execute(stmt)
            return result.rowcount > 0

        stmt = delete(self._model).where(self._model.id == id)
        result = await self._session.execute(stmt)
        return result.rowcount > 0
