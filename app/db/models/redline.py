from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class RedlineStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    REVIEWED = "reviewed"


class ChangeType(StrEnum):
    ADDITION = "addition"
    DELETION = "deletion"
    SUBSTITUTION = "substitution"
    SCOPE_EXPANSION = "scope_expansion"
    SCOPE_REDUCTION = "scope_reduction"
    AMBIGUITY_INTRODUCTION = "ambiguity_introduction"
    LIABILITY_CHANGE = "liability_change"
    INDEMNITY_CHANGE = "indemnity_change"
    TERMINATION_CHANGE = "termination_change"
    CONFIDENTIALITY_CHANGE = "confidentiality_change"
    DATA_PROTECTION_CHANGE = "data_protection_change"
    GOVERNING_LAW_CHANGE = "governing_law_change"
    COMMERCIAL_TERM_CHANGE = "commercial_term_change"
    OPERATIONAL_OBLIGATION_CHANGE = "operational_obligation_change"


class ReviewStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class RedlineJob(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "redline_jobs"

    matter_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("matters.id", ondelete="CASCADE"), nullable=False, index=True
    )
    base_document_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_versions.id", ondelete="RESTRICT"), nullable=False
    )
    comparison_document_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_versions.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[RedlineStatus] = mapped_column(
        String(20), default=RedlineStatus.PENDING, nullable=False
    )
    model_id: Mapped[str | None] = mapped_column(String(255), default=None)
    prompt_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("prompt_versions.id", ondelete="SET NULL"), default=None, nullable=True
    )
    configuration: Mapped[dict | None] = mapped_column(JSONB, default=None)

    matter: Mapped[Matter] = relationship("Matter", back_populates="redline_jobs", lazy="selectin")
    changes: Mapped[list[RedlineChange]] = relationship(
        "RedlineChange",
        back_populates="redline_job",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    base_version: Mapped[DocumentVersion] = relationship("DocumentVersion", foreign_keys=[base_document_version_id], lazy="selectin")
    comparison_version: Mapped[DocumentVersion] = relationship("DocumentVersion", foreign_keys=[comparison_document_version_id], lazy="selectin")
    prompt_version: Mapped[PromptVersion | None] = relationship("PromptVersion", back_populates="redline_jobs", lazy="selectin")

    def __repr__(self) -> str:
        return f"<RedlineJob id={self.id} status={self.status!r}>"


class RedlineChange(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "redline_changes"

    redline_job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("redline_jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    section_path: Mapped[str | None] = mapped_column(String(1000), default=None)
    change_type: Mapped[ChangeType] = mapped_column(String(50), nullable=False)
    original_text: Mapped[str | None] = mapped_column(Text, default=None)
    proposed_text: Mapped[str | None] = mapped_column(Text, default=None)
    rationale: Mapped[str | None] = mapped_column(Text, default=None)
    risk_level: Mapped[str | None] = mapped_column(String(50), default=None)
    confidence: Mapped[float | None] = mapped_column(Float, default=None)
    review_status: Mapped[ReviewStatus] = mapped_column(
        String(20), default=ReviewStatus.PENDING, nullable=False
    )
    approved_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None, nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    source_citations: Mapped[dict | None] = mapped_column(JSONB, default=None)

    redline_job: Mapped[RedlineJob] = relationship("RedlineJob", back_populates="changes", lazy="selectin")
    approved_by: Mapped[User | None] = relationship("User", lazy="selectin")

    def __repr__(self) -> str:
        return f"<RedlineChange id={self.id} type={self.change_type!r} review={self.review_status!r}>"
