from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime
from sqlalchemy import Float
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
    from app.db.models.matter import Matter
    from app.db.models.meeting import Meeting
    from app.db.models.prompt import PromptVersion
    from app.db.models.user import User


class AnalysisStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    APPROVED = "approved"
    REJECTED = "rejected"


class AnalysisType(StrEnum):
    FULL_MEETING = "full_meeting"
    EXECUTIVE_SUMMARY = "executive_summary"
    LEGAL_SUMMARY = "legal_summary"
    RISK_ASSESSMENT = "risk_assessment"
    OBLIGATION_EXTRACTION = "obligation_extraction"
    CUSTOM = "custom"


class ItemType(StrEnum):
    DECISION = "decision"
    RISK = "risk"
    OBLIGATION = "obligation"
    DEADLINE = "deadline"
    TASK = "task"
    QUESTION = "question"
    ASSUMPTION = "assumption"
    NEGOTIATION_POSITION = "negotiation_position"


class Analysis(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "analyses"

    matter_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("matters.id", ondelete="CASCADE"), nullable=False, index=True
    )
    meeting_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("meetings.id", ondelete="SET NULL"), default=None, nullable=True
    )
    analysis_type: Mapped[AnalysisType] = mapped_column(
        String(30), default=AnalysisType.FULL_MEETING, nullable=False
    )
    status: Mapped[AnalysisStatus] = mapped_column(
        String(20), default=AnalysisStatus.PENDING, nullable=False
    )
    model_id: Mapped[str | None] = mapped_column(String(255), default=None)
    prompt_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("prompt_versions.id", ondelete="SET NULL"), default=None, nullable=True
    )
    analysis_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    approved_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None, nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    parameters: Mapped[dict | None] = mapped_column(JSONB, default=None)
    result_metadata: Mapped[dict | None] = mapped_column(JSONB, default=None)

    matter: Mapped[Matter] = relationship("Matter", back_populates="analyses", lazy="selectin")
    meeting: Mapped[Meeting] = relationship("Meeting", back_populates="analyses", lazy="selectin")
    items: Mapped[list[AnalysisItem]] = relationship(
        "AnalysisItem",
        back_populates="analysis",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    model_runs: Mapped[list[ModelRun]] = relationship(
        "ModelRun",
        back_populates="analysis",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    citations: Mapped[list[Citation]] = relationship(
        "Citation",
        back_populates="analysis",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    prompt_version: Mapped[PromptVersion | None] = relationship(
        "PromptVersion", back_populates="analyses", lazy="selectin"
    )
    approved_by: Mapped[User | None] = relationship("User", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Analysis id={self.id} type={self.analysis_type!r} status={self.status!r}>"


class AnalysisItem(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "analysis_items"

    analysis_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    item_type: Mapped[ItemType] = mapped_column(String(30), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, default=None)
    severity: Mapped[str | None] = mapped_column(String(50), default=None)
    status: Mapped[str | None] = mapped_column(String(50), default=None)
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    responsible_party: Mapped[str | None] = mapped_column(String(500), default=None)
    structured_payload: Mapped[dict | None] = mapped_column(JSONB, default=None)
    confidence_score: Mapped[float | None] = mapped_column(Float, default=None)

    analysis: Mapped[Analysis] = relationship("Analysis", back_populates="items", lazy="selectin")
    citations: Mapped[list[Citation]] = relationship(
        "Citation",
        back_populates="item",
        lazy="selectin",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<AnalysisItem id={self.id} type={self.item_type!r} title={self.title!r}>"


class Citation(Base, UUIDMixin):
    __tablename__ = "citations"

    analysis_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    item_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("analysis_items.id", ondelete="SET NULL"), default=None, nullable=True
    )
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer, default=None)
    start_offset: Mapped[int | None] = mapped_column(Integer, default=None)
    end_offset: Mapped[int | None] = mapped_column(Integer, default=None)
    quoted_text: Mapped[str | None] = mapped_column(Text, default=None)
    relevance_score: Mapped[float | None] = mapped_column(Float, default=None)

    analysis: Mapped[Analysis] = relationship(
        "Analysis", back_populates="citations", lazy="selectin"
    )
    item: Mapped[AnalysisItem | None] = relationship(
        "AnalysisItem", back_populates="citations", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Citation id={self.id} source_type={self.source_type!r}>"


class ModelRun(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "model_runs"

    analysis_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    model_name: Mapped[str] = mapped_column(String(255), nullable=False)
    model_version: Mapped[str | None] = mapped_column(String(100), default=None)
    temperature: Mapped[float | None] = mapped_column(Float, default=None)
    token_budget: Mapped[int | None] = mapped_column(Integer, default=None)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    latency_ms: Mapped[int | None] = mapped_column(Integer, default=None)
    hardware_profile: Mapped[str | None] = mapped_column(String(255), default=None)
    failure_reason: Mapped[str | None] = mapped_column(Text, default=None)

    analysis: Mapped[Analysis] = relationship(
        "Analysis", back_populates="model_runs", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<ModelRun id={self.id} model={self.model_name!r}>"
