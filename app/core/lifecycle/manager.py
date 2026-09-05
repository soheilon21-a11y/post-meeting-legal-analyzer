from __future__ import annotations

from app.core.config.settings import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class LifecycleManager:
    def __init__(self) -> None:
        self._initialized = False

    async def startup(self) -> None:
        if self._initialized:
            return

        settings = get_settings()
        logger.info(
            "application_starting",
            app_name=settings.app.name,
            env=settings.app.env,
        )

        await self._check_postgres()
        await self._check_qdrant()
        await self._check_redis()
        await self._check_ollama()

        self._initialized = True
        logger.info("application_started", status="healthy")

    async def shutdown(self) -> None:
        logger.info("application_stopping")
        self._initialized = False
        logger.info("application_stopped")

    async def _check_postgres(self) -> None:
        try:
            from sqlalchemy import text
            from sqlalchemy.ext.asyncio import create_async_engine

            settings = get_settings().postgres
            engine = create_async_engine(settings.database_url, echo=False)
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            await engine.dispose()
            logger.info("postgres_connected", host=settings.host, port=settings.port)
        except Exception as exc:
            logger.warning("postgres_connection_failed", error=str(exc))

    async def _check_qdrant(self) -> None:
        settings = get_settings().qdrant
        if settings.local_path:
            logger.info("qdrant_local_mode", path=settings.local_path)
            return
        try:
            import httpx

            async with httpx.AsyncClient() as client:
                response = await client.get(f"{settings.url}/health", timeout=5.0)
                response.raise_for_status()
            logger.info("qdrant_connected", host=settings.host, port=settings.port)
        except Exception as exc:
            logger.warning("qdrant_connection_failed", error=str(exc))

    async def _check_redis(self) -> None:
        try:
            import redis.asyncio as aioredis

            settings = get_settings().redis
            client = aioredis.from_url(settings.url)
            await client.ping()
            await client.aclose()
            logger.info("redis_connected", host=settings.host, port=settings.port)
        except Exception as exc:
            logger.warning("redis_connection_failed", error=str(exc))

    async def _check_ollama(self) -> None:
        try:
            import httpx

            settings = get_settings().ollama
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{settings.base_url}/api/tags", timeout=5.0)
                response.raise_for_status()
            logger.info("ollama_connected", host=settings.base_url)
        except Exception as exc:
            logger.warning("ollama_connection_failed", error=str(exc))
