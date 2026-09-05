from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.analyses import router as analyses_router
from app.api.v1.corpus import router as corpus_router
from app.api.v1.health import router as health_router
from app.api.v1.redline import router as redline_router

v1_router = APIRouter(prefix="/api/v1")

v1_router.include_router(health_router)
v1_router.include_router(analyses_router)
v1_router.include_router(corpus_router)
v1_router.include_router(redline_router)

__all__ = ["v1_router"]
