from app.domain.document.enums import ProcessingStatus
from app.domain.exceptions.lifecycle import InvalidStateTransition


def ensure_document_can_change(legal_hold: bool) -> None:
    if legal_hold:
        raise ValueError("A document under legal hold cannot be changed")


def ensure_processing_transition(current: ProcessingStatus, requested: ProcessingStatus) -> None:
    allowed = {
        ProcessingStatus.PENDING: {ProcessingStatus.PROCESSING, ProcessingStatus.FAILED},
        ProcessingStatus.PROCESSING: {ProcessingStatus.COMPLETED, ProcessingStatus.FAILED},
        ProcessingStatus.FAILED: {ProcessingStatus.PROCESSING},
        ProcessingStatus.COMPLETED: set(),
    }
    if requested not in allowed[current]:
        raise InvalidStateTransition("DocumentVersion", current, requested)
