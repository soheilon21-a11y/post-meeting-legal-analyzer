from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.middleware.audit import AuditMiddleware
from app.api.middleware.request_id import RequestIdMiddleware
from app.api.middleware.timing import TimingMiddleware
from app.api.v1.router import v1_router
from app.application.exceptions.base import ApplicationError
from app.core.config import get_settings
from app.core.exceptions.domain import AppError
from app.core.exceptions.handlers import app_error_handler
from app.core.exceptions.handlers import generic_exception_handler
from app.core.lifecycle.manager import LifecycleManager
from app.core.logging import configure_logging

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

_lifecycle = LifecycleManager()


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    await _lifecycle.startup()
    yield
    await _lifecycle.shutdown()


def create_app() -> FastAPI:
    settings = get_settings()

    configure_logging(settings.logging)

    app = FastAPI(
        title=settings.app.name,
        version="0.1.0",
        description=(
            "Privacy-first LegalTech platform for analyzing legal meeting "
            "outputs using local AI"
        ),
        docs_url="/docs" if settings.app.debug else None,
        redoc_url="/redoc" if settings.app.debug else None,
        lifespan=_lifespan,
    )

    _configure_middleware(app)
    _configure_exception_handlers(app)
    _configure_routes(app)

    return app


def _configure_middleware(app: FastAPI) -> None:
    settings = get_settings()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=(settings.app.debug and ["*"]) or [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(AuditMiddleware)
    app.add_middleware(TimingMiddleware)


def _configure_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(ApplicationError, _application_error_handler)
    app.add_exception_handler(Exception, generic_exception_handler)


async def _application_error_handler(request, exc: ApplicationError) -> JSONResponse:
    from http import HTTPStatus

    return JSONResponse(
        status_code=HTTPStatus.SERVICE_UNAVAILABLE,
        content={
            "type": "https://tools.ietf.org/html/rfc7231#section-6",
            "title": "Service unavailable",
            "status": HTTPStatus.SERVICE_UNAVAILABLE,
            "detail": exc.message,
        },
    )


def _configure_routes(app: FastAPI) -> None:
    app.include_router(v1_router)


__all__ = ["create_app"]
