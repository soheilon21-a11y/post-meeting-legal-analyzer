from __future__ import annotations

from app.application.exceptions.base import ApplicationError


class ConflictError(ApplicationError):
    code = "application_conflict"

    def __init__(self, resource: str, reason: str) -> None:
        super().__init__(
            f"Conflict for {resource}: {reason}",
            context={"resource": resource, "reason": reason},
        )
