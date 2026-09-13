from __future__ import annotations

import uuid
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from app.db.base import Base
from app.db.base import TimestampMixin
from app.db.base import UUIDMixin

if TYPE_CHECKING:
    from app.db.models.organization import Organization
    from app.db.models.user import User


class AuditEventType(StrEnum):
    LOGIN = "login"
    LOGOUT = "logout"
    AUTH_REGISTERED = "auth.registered"
    AUTH_LOGIN_SUCCESS = "auth.login_success"
    AUTH_LOGIN_FAILED = "auth.login_failed"
    DOCUMENT_UPLOAD = "document_upload"
    DOCUMENT_DOWNLOAD = "document_download"
    DOCUMENT_DELETE = "document_delete"
    MEETING_CREATE = "meeting_create"
    ANALYSIS_REQUEST = "analysis_request"
    ANALYSIS_APPROVE = "analysis_approve"
    ANALYSIS_REJECT = "analysis_reject"
    REDLINE_CREATE = "redline_create"
    REDLINE_GENERATE = "redline_generate"
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
    # Actor identity snapshot: attribution survives a later user (soft)
    # deletion because email is copied onto the row at write time.
    actor_email: Mapped[str | None] = mapped_column(String(320), default=None)
    event_type: Mapped[AuditEventType] = mapped_column(String(50), nullable=False)
    resource_type: Mapped[str | None] = mapped_column(String(100), default=None)
    resource_id: Mapped[uuid.UUID | None] = mapped_column(default=None, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column("metadata", JSONB, default=None)
    client_ip: Mapped[str | None] = mapped_column(String(45), default=None)
    # Append-only hash chain: row_hash = sha256(prev_hash + canonical JSON of
    # the row), seq is monotonic across the whole table, and a DB trigger (see
    # the audit-hash-chain alembic migration) rejects UPDATE/DELETE.
    prev_hash: Mapped[str | None] = mapped_column(String(64), default=None)
    row_hash: Mapped[str | None] = mapped_column(String(64), default=None)
    seq: Mapped[int | None] = mapped_column(Integer, default=None, index=True)

    organization: Mapped[Organization] = relationship(
        "Organization", back_populates="audit_events", lazy="selectin"
    )
    actor: Mapped[User | None] = relationship(
        "User", back_populates="audit_events", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<AuditEvent id={self.id} type={self.event_type!r}>"
