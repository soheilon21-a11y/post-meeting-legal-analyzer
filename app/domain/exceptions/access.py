from __future__ import annotations

from app.domain.exceptions.base import DomainError


class DomainAccessViolation(DomainError):  # noqa: N818
    code = "domain_access_violation"

    def __init__(self, subject: str, resource: str, action: str) -> None:
        super().__init__(
            f"{subject} is not permitted to {action} {resource}",
            context={"subject": subject, "resource": resource, "action": action},
        )
