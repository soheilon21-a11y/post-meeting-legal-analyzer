from __future__ import annotations

from app.application.exceptions.base import ApplicationError


class IntegrationBoundaryError(ApplicationError):
    code = "integration_boundary_error"

    def __init__(self, boundary: str, reason: str) -> None:
        super().__init__(
            f"Integration boundary '{boundary}' failed: {reason}",
            context={"boundary": boundary, "reason": reason},
        )
