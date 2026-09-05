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
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from app.db.base import Base
from app.db.base import TimestampMixin
from app.db.base import UUIDMixin

if TYPE_CHECKING:
    import uuid
    from datetime import datetime

    from app.db.models.matter import Matter


class AIJobType(StrEnum):
    DOCUMENT_PROCESSING = "document_processing"
    INDEXING = "indexing"
    ANALYSIS = "analysis"
    REDLINING = "redlining"
    REPORT_GENERATION = "report_generation"
    EMBEDDING_GENERATION = "embedding_generation"
    CONVERSATION_RESPONSE = "conversation_response"
    OCR = "ocr"
    CHUNKING = "chunking"


class AIJobStatus(StrEnum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AIJob(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "ai_jobs"

    matter_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("matters.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_type: Mapped[AIJobType] = mapped_column(String(50), nullable=False)
    status: Mapped[AIJobStatus] = mapped_column(
        String(20), default=AIJobStatus.PENDING, nullable=False
    )
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    target_entity_type: Mapped[str | None] = mapped_column(String(100), default=None)
    target_entity_id: Mapped[uuid.UUID | None] = mapped_column(default=None, nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSONB, default=None)
    result: Mapped[dict | None] = mapped_column(JSONB, default=None)
    error_message: Mapped[str | None] = mapped_column(Text, default=None)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    progress_pct: Mapped[float | None] = mapped_column(default=None)
    progress_message: Mapped[str | None] = mapped_column(String(500), default=None)
    worker_id: Mapped[str | None] = mapped_column(String(100), default=None)

    matter: Mapped[Matter] = relationship("Matter", back_populates="ai_jobs", lazy="selectin")

    def __repr__(self) -> str:
        return f"<AIJob id={self.id} type={self.job_type!r} status={self.status!r}>"
