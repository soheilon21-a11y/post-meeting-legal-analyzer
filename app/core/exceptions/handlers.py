from __future__ import annotations

from http import HTTPStatus

from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.exceptions.domain import (
    AppError,
    ConflictError,
    FileTooLargeError,
    FileProcessingError,
    ForbiddenError,
    NotFoundError,
    ProcessingNotCompleteError,
    TokenBudgetExceededError,
    UnauthorizedError,
    UnsupportedFileTypeError,
    ValidationError,
)
from app.core.logging import get_logger

logger = get_logger(__name__)


def _problem_response(
    status: int,
    title: str,
    detail: str | None = None,
    instance: str | None = None,
    extra: dict | None = None,
) -> JSONResponse:
    body: dict = {
        "type": f"https://tools.ietf.org/html/rfc7231#section-{_status_to_section(status)}",
        "title": title,
        "status": status,
    }
    if detail:
        body["detail"] = detail
    if instance:
        body["instance"] = instance
    if extra:
        body.update(extra)
    return JSONResponse(status_code=status, content=body)


def _status_to_section(status: int) -> str:
    return str(status // 100)


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    status_map: dict[type[AppError], int] = {
        NotFoundError: HTTPStatus.NOT_FOUND,
        UnauthorizedError: HTTPStatus.UNAUTHORIZED,
        ForbiddenError: HTTPStatus.FORBIDDEN,
        ConflictError: HTTPStatus.CONFLICT,
        ValidationError: HTTPStatus.UNPROCESSABLE_ENTITY,
        FileProcessingError: HTTPStatus.UNPROCESSABLE_ENTITY,
        UnsupportedFileTypeError: HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
        FileTooLargeError: HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
        ProcessingNotCompleteError: HTTPStatus.ACCEPTED,
        TokenBudgetExceededError: HTTPStatus.PAYLOAD_TOO_LARGE,
    }

    status_code = status_map.get(type(exc), HTTPStatus.INTERNAL_SERVER_ERROR)

    if status_code >= 500:
        logger.exception("Unhandled application error", exc_info=exc)

    return _problem_response(
        status=status_code,
        title=exc.message,
        detail=exc.detail,
        instance=str(request.url),
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception", exc_info=exc)
    return _problem_response(
        status=HTTPStatus.INTERNAL_SERVER_ERROR,
        title="Internal server error",
        detail="An unexpected error occurred",
        instance=str(request.url),
    )
