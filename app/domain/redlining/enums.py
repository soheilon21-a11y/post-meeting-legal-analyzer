from enum import StrEnum


class RedlineStatus(StrEnum):
    DRAFT = "draft"
    PROCESSING = "processing"
    READY_FOR_REVIEW = "ready_for_review"
    REVIEWED = "reviewed"
    EXPORTED = "exported"


class ReviewStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ChangeType(StrEnum):
    ADDITION = "addition"
    DELETION = "deletion"
    SUBSTITUTION = "substitution"
    SCOPE_CHANGE = "scope_change"
    LIABILITY_CHANGE = "liability_change"
    INDEMNITY_CHANGE = "indemnity_change"
    TERMINATION_CHANGE = "termination_change"
    CONFIDENTIALITY_CHANGE = "confidentiality_change"
    DATA_PROTECTION_CHANGE = "data_protection_change"
    GOVERNING_LAW_CHANGE = "governing_law_change"
    COMMERCIAL_TERM_CHANGE = "commercial_term_change"
