from __future__ import annotations

from app.application.exceptions.base import ApplicationError


class ProcessingError(ApplicationError):
    code = "processing_error"

    def __init__(self, operation: str, reason: str) -> None:
        super().__init__(
            f"Application operation '{operation}' failed: {reason}",
            context={"operation": operation, "reason": reason},
        )
