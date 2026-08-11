from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings


def _create_engine():
    settings = get_settings().postgres
    return create_async_engine(
        settings.database_url,
        echo=settings.echo,
        pool_size=settings.pool_size,
        max_overflow=settings.pool_overflow,
        pool_pre_ping=True,
    )


_engine = _create_engine()
_async_session_factory = async_sessionmaker(
    _engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with _async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def dispose_engine() -> None:
    await _engine.dispose()
