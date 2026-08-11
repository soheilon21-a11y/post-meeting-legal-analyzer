from __future__ import annotations

import uuid
from enum import StrEnum

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin


class ConversationRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class Conversation(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "conversations"

    matter_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("matters.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None, nullable=True
    )

    matter: Mapped[Matter] = relationship("Matter", back_populates="conversations", lazy="selectin")
    messages: Mapped[list[ConversationMessage]] = relationship(
        "ConversationMessage",
        back_populates="conversation",
        lazy="selectin",
        cascade="all, delete-orphan",
        order_by="ConversationMessage.sequence_number",
    )
    created_by: Mapped[User | None] = relationship("User", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Conversation id={self.id} title={self.title!r}>"


class ConversationMessage(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "conversation_messages"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[ConversationRole] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sequence_number: Mapped[int] = mapped_column(default=0, nullable=False)
    model_name: Mapped[str | None] = mapped_column(String(255), default=None)
    token_count: Mapped[int | None] = mapped_column(default=None)
    retrieval_sources: Mapped[dict | None] = mapped_column(JSONB, default=None, nullable=True)

    conversation: Mapped[Conversation] = relationship(
        "Conversation", back_populates="messages", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<ConversationMessage id={self.id} role={self.role!r} seq={self.sequence_number}>"
