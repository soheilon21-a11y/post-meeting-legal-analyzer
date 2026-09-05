from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from app.db.base import Base
from app.db.base import TimestampMixin
from app.db.base import UUIDMixin

if TYPE_CHECKING:
    from datetime import datetime

    from app.db.models.analysis import Analysis
    from app.db.models.matter import Matter


class SourceType(StrEnum):
    AUDIO = "audio"
    VIDEO = "video"
    TEXT = "text"
    DOCX = "docx"
    PDF = "pdf"
    MARKDOWN = "markdown"
    PLAINTEXT = "plaintext"


class Meeting(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "meetings"

    matter_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("matters.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    meeting_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    duration_seconds: Mapped[int | None] = mapped_column(Integer, default=None)
    source_type: Mapped[SourceType] = mapped_column(
        String(20), default=SourceType.TEXT, nullable=False
    )
    agenda: Mapped[str | None] = mapped_column(Text, default=None)
    attendees_raw: Mapped[str | None] = mapped_column(Text, default=None)
    uploaded_by_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None, nullable=True
    )

    matter: Mapped[Matter] = relationship("Matter", back_populates="meetings", lazy="selectin")
    transcript_segments: Mapped[list[TranscriptSegment]] = relationship(
        "TranscriptSegment",
        back_populates="meeting",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    analyses: Mapped[list[Analysis]] = relationship(
        "Analysis", back_populates="meeting", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Meeting id={self.id} title={self.title!r}>"


class TranscriptSegment(Base, UUIDMixin):
    __tablename__ = "transcript_segments"

    meeting_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    speaker: Mapped[str | None] = mapped_column(String(255), default=None)
    start_time: Mapped[float | None] = mapped_column(default=None)
    end_time: Mapped[float | None] = mapped_column(default=None)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)

    meeting: Mapped[Meeting] = relationship(
        "Meeting", back_populates="transcript_segments", lazy="selectin"
    )

    def __repr__(self) -> str:
        return (
            f"<TranscriptSegment id={self.id} meeting_id={self.meeting_id} "
            f"seq={self.sequence_number}>"
        )
