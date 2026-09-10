"""Idempotent dev-data seed for the redline API.

Creates (deterministic UUIDs derived from the handle names, re-running is a
no-op that only prints the current ids):

- Organization  handle 'org-1'
- User          handle 'test-user-1' (display_name), member of org-1
- Matter        handle 'matter-1' (matter_number), EDIT membership for the user
- Documents     'dev-base-doc' + 'dev-comparison-doc', one version each

Usage:
    python scripts/seed_dev_data.py

    # mint a token whose subject resolves by display_name / org name:
    python -c "from app.core.security.tokens import TokenService; \\
print(TokenService().create_access_token('test-user-1','org-1'))"

    # create a redline job (matter resolved by matter_number):
    curl -X POST http://localhost:8000/api/v1/redlines/ -H "Authorization: Bearer <token>" \\
      -H "Content-Type: application/json" \\
      -d '{"matter_id":"matter-1","base_document_id":"<base_version_id>",\\
"comparison_document_id":"<comparison_version_id>","deterministic_seed":42}'
"""
from __future__ import annotations

import asyncio
import hashlib
import sys
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings
from app.db.base import Base
from app.db.models import Document
from app.db.models import DocumentClassification
from app.db.models import DocumentSegment
from app.db.models import DocumentType
from app.db.models import DocumentVersion
from app.db.models import Matter
from app.db.models import MatterClassification
from app.db.models import MatterMember
from app.db.models import MatterMemberRole
from app.db.models import MatterStatus
from app.db.models import Organization
from app.db.models import ProcessingStatus
from app.db.models import User

_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "post-meeting-legal-analyzer.dev-seed")


def _handle_uuid(handle: str) -> uuid.UUID:
    return uuid.uuid5(_NAMESPACE, handle)


async def seed() -> None:
    engine = create_async_engine(get_settings().postgres.database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)

    org_id = _handle_uuid("org-1")
    user_id = _handle_uuid("test-user-1")
    matter_id = _handle_uuid("matter-1")

    async with maker() as session:
        org = await session.get(Organization, org_id)
        if org is None:
            org = Organization(id=org_id, name="org-1")
            session.add(org)

        user = await session.get(User, user_id)
        if user is None:
            user = User(
                id=user_id,
                organization_id=org.id,
                email="test-user-1@dev.local",
                display_name="test-user-1",
                hashed_password="dev-seed-not-a-real-password",
            )
            session.add(user)

        matter = await session.get(Matter, matter_id)
        if matter is None:
            matter = Matter(
                id=matter_id,
                organization_id=org.id,
                name="Dev Supplier Agreement Matter",
                matter_number="matter-1",
                status=MatterStatus.ACTIVE,
                classification=MatterClassification.GENERAL,
            )
            session.add(matter)

        existing_member = await session.scalar(
            select(MatterMember).where(
                MatterMember.matter_id == matter.id,
                MatterMember.user_id == user.id,
            )
        )
        if existing_member is None:
            session.add(
                MatterMember(
                    matter_id=matter.id,
                    user_id=user.id,
                    role=MatterMemberRole.EDITOR,
                )
            )

        version_texts = {
            "dev-base-doc": (
                "Payment is due within 30 days of invoice receipt.",
                "Supplier liability is capped at direct damages.",
            ),
            "dev-comparison-doc": (
                "Payment is due within 45 days of invoice receipt.",
                "Supplier liability covers direct damages and reasonable attorney fees.",
            ),
        }
        version_ids: dict[str, uuid.UUID] = {}
        for handle, title in (("dev-base-doc", "Supplier Agreement v1"),
                              ("dev-comparison-doc", "Supplier Agreement v2")):
            doc_id = _handle_uuid(handle)
            document = await session.get(Document, doc_id)
            if document is None:
                document = Document(
                    id=doc_id,
                    matter_id=matter.id,
                    document_type=DocumentType.CONTRACT,
                    title=title,
                    source_filename=f"{handle}.txt",
                    mime_type="text/plain",
                    sha256_hash=_handle_uuid(f"{handle}-sha").hex,
                    classification=DocumentClassification.PUBLIC,
                    created_by_id=user.id,
                )
                session.add(document)
            version = document.versions[-1] if document.versions else None
            if version is None:
                version = DocumentVersion(
                    id=_handle_uuid(f"{handle}-v1"),
                    document_id=document.id,
                    version_number=1,
                    object_storage_key=f"dev/{handle}/v1",
                    page_count=1,
                    processing_status=ProcessingStatus.COMPLETED,
                    uploader_id=user.id,
                )
                session.add(version)
                await session.flush()

            existing = await session.scalar(
                select(DocumentSegment.id)
                .where(DocumentSegment.document_version_id == version.id)
                .limit(1)
            )
            if existing is None:
                offset = 0
                for paragraph, text in enumerate(version_texts[handle], start=1):
                    session.add(
                        DocumentSegment(
                            document_version_id=version.id,
                            page_number=1,
                            paragraph_number=paragraph,
                            text=text,
                            char_start=offset,
                            char_end=offset + len(text),
                            content_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
                        )
                    )
                    offset += len(text) + 1
            version_ids[handle] = version.id

        await session.commit()

    await engine.dispose()

    print("Seeded dev data (idempotent):")
    print(f"  org-1                     organization_id = {org_id}")
    print(f"  test-user-1 (EDITOR)      user_id         = {user_id}")
    print(f"  matter-1                  matter_id       = {matter_id}")
    print(f"  base version id                           = {version_ids['dev-base-doc']}")
    print(f"  comparison version id                     = {version_ids['dev-comparison-doc']}")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(seed())
