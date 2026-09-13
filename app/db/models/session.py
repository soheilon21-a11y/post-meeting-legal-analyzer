from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from app.db.base import Base
from app.db.base import TimestampMixin

if TYPE_CHECKING:
    from app.db.models.user import User


class Session(Base, TimestampMixin):
    """Server-side session backing the long-lived ``local_session`` cookie.

    ``session_id`` doubles as the ``jti`` claim of the session JWT: the token
    is only accepted while this row exists, is not revoked and has not passed
    ``expires_at``.  That is what makes POST /auth/logout and server-side
    revocation effective immediately, independent of the JWT's own expiry.
    """

    __tablename__ = "sessions"

    session_id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        sort_order=-100,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    user: Mapped[User] = relationship("User", lazy="selectin")

    def __repr__(self) -> str:
        return (
            f"<Session id={self.session_id} user_id={self.user_id} "
            f"revoked={self.revoked}>"
        )
