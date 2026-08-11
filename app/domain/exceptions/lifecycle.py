from __future__ import annotations

from typing import Any

from app.domain.exceptions.base import DomainError


class InvalidStateTransition(DomainError):  # noqa: N818
    code = "invalid_state_transition"

    def __init__(self, entity: str, current_state: Any, requested_state: Any) -> None:
        super().__init__(
            f"{entity} cannot transition from {current_state!s} to {requested_state!s}",
            context={
                "entity": entity,
                "current_state": str(current_state),
                "requested_state": str(requested_state),
            },
        )
