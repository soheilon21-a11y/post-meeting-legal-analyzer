from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class PromptVersion(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "prompt_versions"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    user_prompt_template: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, default=None)
    model_constraints: Mapped[dict | None] = mapped_column(JSONB, default=None)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sha256_hash: Mapped[str | None] = mapped_column(String(64), default=None)
    change_description: Mapped[str | None] = mapped_column(Text, default=None)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None, nullable=True
    )
    parent_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("prompt_versions.id", ondelete="SET NULL"), default=None, nullable=True
    )

    analyses: Mapped[list[Analysis]] = relationship(
        "Analysis", back_populates="prompt_version", lazy="selectin"
    )
    redline_jobs: Mapped[list[RedlineJob]] = relationship(
        "RedlineJob", back_populates="prompt_version", lazy="selectin"
    )
    created_by: Mapped[User | None] = relationship("User", lazy="selectin")

    def __repr__(self) -> str:
        return f"<PromptVersion id={self.id} name={self.name!r} v{self.version}>"


class Embedding(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "embeddings"

    document_segment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("document_segments.id", ondelete="CASCADE"), default=None, nullable=True
    )
    matter_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("matters.id", ondelete="CASCADE"), nullable=False, index=True
    )
    model_name: Mapped[str] = mapped_column(String(255), nullable=False)
    model_version: Mapped[str | None] = mapped_column(String(100), default=None)
    embedding_dimension: Mapped[int] = mapped_column(Integer, nullable=False)
    qdrant_point_id: Mapped[str | None] = mapped_column(String(100), default=None, unique=True)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    token_count: Mapped[int | None] = mapped_column(Integer, default=None)
    chunk_index: Mapped[int | None] = mapped_column(Integer, default=None)
    metadata_json: Mapped[dict | None] = mapped_column("metadata", JSONB, default=None)

    document_segment: Mapped[DocumentSegment | None] = relationship(
        "DocumentSegment", back_populates="embeddings", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Embedding id={self.id} model={self.model_name!r}>"
