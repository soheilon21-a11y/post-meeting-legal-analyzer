from __future__ import annotations

from typing import Any

from app.domain.exceptions.base import DomainError


class InvariantViolation(DomainError):  # noqa: N818
    code = "invariant_violation"

    def __init__(self, message: str, *, field_name: str | None = None, **context: Any) -> None:
        if field_name is not None:
            context["field_name"] = field_name
        super().__init__(message, context=context)
