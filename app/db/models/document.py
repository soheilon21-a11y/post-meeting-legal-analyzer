from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin


class DocumentType(StrEnum):
    CONTRACT = "contract"
    POLICY = "policy"
    CORRESPONDENCE = "correspondence"
    PLEADING = "pleading"
    TRANSCRIPT = "transcript"
    NOTE = "note"
    REPORT = "report"
    OTHER = "other"


class ProcessingStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class DocumentClassification(StrEnum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    PRIVILEGED = "privileged"


class Document(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "documents"

    matter_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("matters.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_type: Mapped[DocumentType] = mapped_column(
        Enum(DocumentType, name="document_type"),
        default=DocumentType.OTHER,
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    source_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(127), nullable=False)
    sha256_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    classification: Mapped[DocumentClassification] = mapped_column(
        Enum(DocumentClassification, name="document_classification"),
        default=DocumentClassification.INTERNAL,
        nullable=False,
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None, nullable=True
    )
    is_privileged: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    legal_hold: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    matter: Mapped[Matter] = relationship("Matter", back_populates="documents", lazy="selectin")
    versions: Mapped[list[DocumentVersion]] = relationship(
        "DocumentVersion", back_populates="document", lazy="selectin", cascade="all, delete-orphan"
    )
    created_by: Mapped[User | None] = relationship("User", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Document id={self.id} title={self.title!r}>"


class DocumentVersion(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "document_versions"

    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    object_storage_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    extracted_text_key: Mapped[str | None] = mapped_column(String(1024), default=None)
    page_count: Mapped[int | None] = mapped_column(Integer, default=None)
    processing_status: Mapped[ProcessingStatus] = mapped_column(
        Enum(ProcessingStatus, name="processing_status"),
        default=ProcessingStatus.PENDING,
        nullable=False,
    )
    processing_error: Mapped[str | None] = mapped_column(Text, default=None)
    uploader_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None, nullable=True
    )

    document: Mapped[Document] = relationship("Document", back_populates="versions", lazy="selectin")
    segments: Mapped[list[DocumentSegment]] = relationship(
        "DocumentSegment",
        back_populates="document_version",
        lazy="selectin",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<DocumentVersion id={self.id} doc_id={self.document_id} v{self.version_number}>"


class DocumentSegment(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "document_segments"

    document_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    page_number: Mapped[int | None] = mapped_column(Integer, default=None)
    paragraph_number: Mapped[int | None] = mapped_column(Integer, default=None)
    section_path: Mapped[str | None] = mapped_column(String(1000), default=None)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    char_start: Mapped[int | None] = mapped_column(Integer, default=None)
    char_end: Mapped[int | None] = mapped_column(Integer, default=None)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    document_version: Mapped[DocumentVersion] = relationship(
        "DocumentVersion", back_populates="segments", lazy="selectin"
    )
    embeddings: Mapped[list[Embedding]] = relationship(
        "Embedding", back_populates="document_segment", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<DocumentSegment id={self.id} section={self.section_path!r}>"
