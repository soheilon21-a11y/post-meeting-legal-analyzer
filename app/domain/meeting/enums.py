from enum import StrEnum


class MeetingSource(StrEnum):
    TEXT = "text"
    AUDIO = "audio"
    VIDEO = "video"
    PDF = "pdf"
    DOCX = "docx"
    MARKDOWN = "markdown"


class MeetingStatus(StrEnum):
    DRAFT = "draft"
    TRANSCRIBING = "transcribing"
    READY = "ready"
    ARCHIVED = "archived"
