from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

from app.domain.exceptions.base import DomainError


class MissingEvidence(DomainError):  # noqa: N818
    code = "missing_evidence"

    def __init__(self, claim: str, required_sources: Sequence[str] | None = None) -> None:
        super().__init__(
            f"The claim '{claim}' requires supporting evidence",
            context={
                "claim": claim,
                "required_sources": list(required_sources or []),
            },
        )
