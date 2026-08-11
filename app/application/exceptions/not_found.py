from __future__ import annotations

from app.application.exceptions.base import ApplicationError


class ResourceNotFound(ApplicationError):  # noqa: N818
    code = "resource_not_found"

    def __init__(self, resource: str, identifier: str) -> None:
        super().__init__(
            f"{resource} '{identifier}' was not found",
            context={"resource": resource, "identifier": identifier},
        )
