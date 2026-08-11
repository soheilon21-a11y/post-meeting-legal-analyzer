from app.domain.exceptions.redlining import UnsafeRedlineOperation
from app.domain.redlining.enums import RedlineStatus
from app.domain.redlining.enums import ReviewStatus


def ensure_change_can_be_approved(review_status: ReviewStatus, original_text: str) -> None:
    if review_status is not ReviewStatus.PENDING:
        raise UnsafeRedlineOperation("approve_change", "change has already been reviewed")
    if not original_text.strip():
        raise UnsafeRedlineOperation("approve_change", "original source text is missing")


def ensure_job_can_be_exported(status: RedlineStatus, pending_changes: int) -> None:
    if status is not RedlineStatus.REVIEWED:
        raise UnsafeRedlineOperation("export", "all changes must be reviewed")
    if pending_changes:
        raise UnsafeRedlineOperation("export", "pending changes remain")
