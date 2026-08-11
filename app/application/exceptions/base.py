from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

if TYPE_CHECKING:
    from collections.abc import Mapping


class ApplicationError(Exception):
    """Base exception for application orchestration failures."""

    code = "application_error"

    def __init__(self, message: str, *, context: Mapping[str, Any] | None = None) -> None:
        self.message = message
        self.context = dict(context or {})
        super().__init__(message)
