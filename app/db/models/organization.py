from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from app.db.base import Base
from app.db.base import SoftDeleteMixin
from app.db.base import TimestampMixin
from app.db.base import UUIDMixin

if TYPE_CHECKING:
    from app.db.models.audit import AuditEvent
    from app.db.models.matter import Matter
    from app.db.models.user import User


class Organization(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    retention_policy_days: Mapped[int | None] = mapped_column(default=None)
    encryption_key_reference: Mapped[str | None] = mapped_column(String(512), default=None)

    users: Mapped[list[User]] = relationship(
        "User", back_populates="organization", lazy="selectin"
    )
    matters: Mapped[list[Matter]] = relationship(
        "Matter", back_populates="organization", lazy="selectin"
    )
    audit_events: Mapped[list[AuditEvent]] = relationship(
        "AuditEvent", back_populates="organization", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Organization id={self.id} name={self.name!r}>"
