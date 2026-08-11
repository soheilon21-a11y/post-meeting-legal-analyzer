from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.application.exceptions.validation import ApplicationValidationError

if TYPE_CHECKING:
    from app.application.dtos.internal.security import ActorContext


@dataclass(frozen=True, slots=True)
class CreateRedlineRequest:
    matter_id: str
    base_document_id: str
    comparison_document_id: str
    actor: ActorContext
    deterministic_seed: int = 0

    def __post_init__(self) -> None:
        for field_name, value in (
            ("matter_id", self.matter_id),
            ("base_document_id", self.base_document_id),
            ("comparison_document_id", self.comparison_document_id),
        ):
            if not value.strip():
                raise ApplicationValidationError(
                    f"{field_name} must not be blank", field=field_name
                )


@dataclass(frozen=True, slots=True)
class ReviewRedlineChangeRequest:
    redline_job_id: str
    change_id: str
    approve: bool
    actor: ActorContext
