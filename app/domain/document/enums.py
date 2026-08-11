from enum import StrEnum


class DocumentType(StrEnum):
    CONTRACT = "contract"
    POLICY = "policy"
    CORRESPONDENCE = "correspondence"
    TRANSCRIPT = "transcript"
    NOTE = "note"
    REPORT = "report"
    OTHER = "other"


class DocumentClassification(StrEnum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    PRIVILEGED = "privileged"


class ProcessingStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
