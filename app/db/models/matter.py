from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime
from sqlalchemy import Enum
from sqlalchemy import ForeignKey
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from app.db.base import Base
from app.db.base import SoftDeleteMixin
from app.db.base import TimestampMixin
from app.db.base import UUIDMixin

if TYPE_CHECKING:
    import uuid
    from datetime import datetime

    from app.db.models.ai_job import AIJob
    from app.db.models.analysis import Analysis
    from app.db.models.conversation import Conversation
    from app.db.models.document import Document
    from app.db.models.meeting import Meeting
    from app.db.models.organization import Organization
    from app.db.models.redline import RedlineJob
    from app.db.models.user import User


class MatterStatus(StrEnum):
    ACTIVE = "active"
    CLOSED = "closed"
    ARCHIVED = "archived"
    ON_HOLD = "on_hold"


class MatterClassification(StrEnum):
    GENERAL = "general"
    CONFIDENTIAL = "confidential"
    PRIVILEGED = "privileged"
    RESTRICTED = "restricted"


class MatterMemberRole(StrEnum):
    OWNER = "owner"
    EDITOR = "editor"
    VIEWER = "viewer"


class Matter(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "matters"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    matter_number: Mapped[str | None] = mapped_column(String(100), unique=True, default=None)
    description: Mapped[str | None] = mapped_column(Text, default=None)
    status: Mapped[MatterStatus] = mapped_column(
        Enum(MatterStatus, name="matter_status"),
        default=MatterStatus.ACTIVE,
        nullable=False,
    )
    classification: Mapped[MatterClassification] = mapped_column(
        Enum(MatterClassification, name="matter_classification"),
        default=MatterClassification.GENERAL,
        nullable=False,
    )
    retention_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    organization: Mapped[Organization] = relationship(
        "Organization", back_populates="matters", lazy="selectin"
    )
    members: Mapped[list[MatterMember]] = relationship(
        "MatterMember", back_populates="matter", lazy="selectin", cascade="all, delete-orphan"
    )
    documents: Mapped[list[Document]] = relationship(
        "Document", back_populates="matter", lazy="selectin"
    )
    meetings: Mapped[list[Meeting]] = relationship(
        "Meeting", back_populates="matter", lazy="selectin"
    )
    analyses: Mapped[list[Analysis]] = relationship(
        "Analysis", back_populates="matter", lazy="selectin"
    )
    redline_jobs: Mapped[list[RedlineJob]] = relationship(
        "RedlineJob", back_populates="matter", lazy="selectin"
    )
    conversations: Mapped[list[Conversation]] = relationship(
        "Conversation", back_populates="matter", lazy="selectin"
    )
    ai_jobs: Mapped[list[AIJob]] = relationship(
        "AIJob", back_populates="matter", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Matter id={self.id} name={self.name!r}>"


class MatterMember(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "matter_members"

    matter_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("matters.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[MatterMemberRole] = mapped_column(
        Enum(MatterMemberRole, name="matter_member_role"),
        default=MatterMemberRole.VIEWER,
        nullable=False,
    )

    matter: Mapped[Matter] = relationship("Matter", back_populates="members", lazy="selectin")
    user: Mapped[User] = relationship("User", back_populates="matter_memberships", lazy="selectin")

    def __repr__(self) -> str:
        return (
            f"<MatterMember matter_id={self.matter_id} "
            f"user_id={self.user_id} role={self.role!r}>"
        )
