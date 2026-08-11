from __future__ import annotations

from typing import Any

from app.application.exceptions.base import ApplicationError


class ApplicationValidationError(ApplicationError):
    code = "application_validation_error"

    def __init__(self, message: str, *, field: str | None = None, **context: Any) -> None:
        if field is not None:
            context["field"] = field
        super().__init__(message, context=context)
