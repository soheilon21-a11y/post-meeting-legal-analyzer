from enum import StrEnum


class MatterStatus(StrEnum):
    ACTIVE = "active"
    ON_HOLD = "on_hold"
    CLOSED = "closed"
    ARCHIVED = "archived"


class MatterClassification(StrEnum):
    GENERAL = "general"
    CONFIDENTIAL = "confidential"
    PRIVILEGED = "privileged"
    RESTRICTED = "restricted"


class MatterMemberRole(StrEnum):
    OWNER = "owner"
    EDITOR = "editor"
    VIEWER = "viewer"
