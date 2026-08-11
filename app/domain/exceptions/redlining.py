from __future__ import annotations

from typing import Any

from app.domain.exceptions.base import DomainError


class UnsafeRedlineOperation(DomainError):  # noqa: N818
    code = "unsafe_redline_operation"

    def __init__(self, operation: str, reason: str, **context: Any) -> None:
        context.update({"operation": operation, "reason": reason})
        super().__init__(f"Redline operation '{operation}' is unsafe: {reason}", context=context)
