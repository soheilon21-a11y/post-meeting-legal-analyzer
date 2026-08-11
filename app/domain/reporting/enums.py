from enum import StrEnum


class ReportStatus(StrEnum):
    DRAFT = "draft"
    GENERATING = "generating"
    READY = "ready"
    APPROVED = "approved"
    EXPORTED = "exported"


class ReportFormat(StrEnum):
    HTML = "html"
    PDF = "pdf"
    DOCX = "docx"
