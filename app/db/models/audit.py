from __future__ import annotations

import uuid
from enum import StrEnum

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class AuditEventType(StrEnum):
    LOGIN = "login"
    LOGOUT = "logout"
    DOCUMENT_UPLOAD = "document_upload"
    DOCUMENT_DOWNLOAD = "document_download"
    DOCUMENT_DELETE = "document_delete"
    MEETING_CREATE = "meeting_create"
    ANALYSIS_REQUEST = "analysis_request"
    ANALYSIS_APPROVE = "analysis_approve"
    ANALYSIS_REJECT = "analysis_reject"
    REDLINE_CREATE = "redline_create"
    REDLINE_APPROVE = "redline_approve"
    REDLINE_REJECT = "redline_reject"
    REPORT_EXPORT = "report_export"
    MATTER_ACCESS = "matter_access"
    MATTER_MODIFY = "matter_modify"
    USER_INVITE = "user_invite"
    PERMISSION_CHANGE = "permission_change"
    DATA_EXPORT = "data_export"
    DATA_DELETE = "data_delete"
    LEGAL_HOLD = "legal_hold"
    RETENTION_ACTION = "retention_action"


class AuditEvent(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "audit_events"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    matter_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("matters.id", ondelete="SET NULL"), default=None, nullable=True
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None, nullable=True
    )
    event_type: Mapped[AuditEventType] = mapped_column(String(50), nullable=False)
    resource_type: Mapped[str | None] = mapped_column(String(100), default=None)
    resource_id: Mapped[uuid.UUID | None] = mapped_column(default=None, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column("metadata", JSONB, default=None)
    client_ip: Mapped[str | None] = mapped_column(String(45), default=None)

    organization: Mapped[Organization] = relationship(
        "Organization", back_populates="audit_events", lazy="selectin"
    )
    actor: Mapped[User | None] = relationship(
        "User", back_populates="audit_events", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<AuditEvent id={self.id} type={self.event_type!r}>"
