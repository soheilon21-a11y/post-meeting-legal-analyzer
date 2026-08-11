from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter(tags=["Health"])


@router.get("/health/live", include_in_schema=False)
async def health_live() -> dict[str, str]:
    return {"status": "alive"}


@router.get("/health/ready", include_in_schema=False)
async def health_ready() -> dict[str, str]:
    return {"status": "ready"}


@router.get("/health", include_in_schema=False)
async def health_check() -> dict[str, Any]:
    settings = get_settings()
    return {
        "status": "healthy",
        "app": settings.app.name,
        "version": "0.1.0",
        "environment": settings.app.env,
    }


@router.get("/health/models", include_in_schema=False)
async def health_models() -> dict[str, Any]:
    try:
        import httpx

        settings = get_settings().ollama
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings.base_url}/api/tags", timeout=10.0
            )
            response.raise_for_status()
            data = response.json()
            models = [m["name"] for m in data.get("models", [])]
    except Exception:
        models = []

    return {
        "ollama_available": len(models) > 0,
        "available_models": models,
        "default_model": get_settings().ollama.default_model,
        "embedding_model": get_settings().ollama.embedding_model,
    }
