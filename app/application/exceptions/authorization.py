from __future__ import annotations

from app.application.exceptions.base import ApplicationError


class AuthorizationError(ApplicationError):
    code = "authorization_error"

    def __init__(self, action: str, resource: str) -> None:
        super().__init__(
            f"Not authorized to {action} {resource}",
            context={"action": action, "resource": resource},
        )


__all__ = ["AuthorizationError"]
