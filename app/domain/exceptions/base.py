from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

if TYPE_CHECKING:
    from collections.abc import Mapping


class DomainError(Exception):
    """Base exception for violations of domain rules."""

    code = "domain_error"

    def __init__(self, message: str, *, context: Mapping[str, Any] | None = None) -> None:
        self.message = message
        self.context = dict(context or {})
        super().__init__(message)
