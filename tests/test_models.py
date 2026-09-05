from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine

from app.db.base import Base
from app.db.models.analysis import Analysis
from app.db.models.analysis import AnalysisItem
from app.db.models.audit import AuditEvent
from app.db.models.document import Document
from app.db.models.document import DocumentSegment
from app.db.models.document import DocumentVersion
from app.db.models.matter import Matter
from app.db.models.matter import MatterMember
from app.db.models.meeting import Meeting
from app.db.models.meeting import TranscriptSegment
from app.db.models.organization import Organization
from app.db.models.redline import RedlineChange
from app.db.models.redline import RedlineJob
from app.db.models.user import User


@pytest.fixture
async def db_session() -> AsyncSession:
    from app.core.config import get_settings

    settings = get_settings()
    engine = create_async_engine(settings.postgres.database_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
def sample_org_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def sample_user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.mark.anyio
async def test_organization_creation(db_session: AsyncSession):
    org = Organization(name="Test Firm")
    db_session.add(org)
    await db_session.flush()

    assert org.id is not None
    assert org.name == "Test Firm"
    assert org.created_at is not None


@pytest.mark.anyio
async def test_matter_with_member(db_session: AsyncSession, sample_org_id, sample_user_id):
    user = User(id=sample_user_id, email="test@example.com", display_name="Test User", organization_id=sample_org_id, hashed_password="hashed")
    org = Organization(id=sample_org_id, name="Test Firm")
    db_session.add_all([org, user])
    await db_session.flush()

    matter = Matter(organization_id=sample_org_id, name="Test Matter")
    db_session.add(matter)
    await db_session.flush()

    membership = MatterMember(
        matter_id=matter.id,
        user_id=sample_user_id,
    )
    db_session.add(membership)
    await db_session.flush()

    assert matter.id is not None
    assert membership.id is not None
    assert membership.matter_id == matter.id
    assert membership.user_id == sample_user_id


@pytest.mark.anyio
async def test_document_with_versions(db_session: AsyncSession, sample_org_id):
    org = Organization(id=sample_org_id, name="Test Firm")
    matter = Matter(organization_id=sample_org_id, name="Test Matter")
    db_session.add_all([org, matter])
    await db_session.flush()

    doc = Document(
        matter_id=matter.id,
        title="Test Contract",
        source_filename="contract.docx",
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        sha256_hash="abc123",
    )
    db_session.add(doc)
    await db_session.flush()

    version = DocumentVersion(
        document_id=doc.id,
        version_number=1,
        object_storage_key="matters/test/contract_v1.docx",
    )
    db_session.add(version)
    await db_session.flush()

    segment = DocumentSegment(
        document_version_id=version.id,
        text="This is a test clause.",
        content_hash="def456",
    )
    db_session.add(segment)
    await db_session.flush()

    assert doc.id is not None
    assert version.document_id == doc.id
    assert segment.document_version_id == version.id


@pytest.mark.anyio
async def test_meeting_with_transcript(db_session: AsyncSession, sample_org_id):
    org = Organization(id=sample_org_id, name="Test Firm")
    matter = Matter(organization_id=sample_org_id, name="Test Matter")
    db_session.add_all([org, matter])
    await db_session.flush()

    meeting = Meeting(
        matter_id=matter.id,
        title="Client Meeting",
        meeting_date=uuid.uuid4(),  # placeholder, replaced below
    )
    from datetime import UTC
    from datetime import datetime

    meeting.meeting_date = datetime.now(UTC)
    db_session.add(meeting)
    await db_session.flush()

    segment = TranscriptSegment(
        meeting_id=meeting.id,
        speaker="John",
        text="Let's discuss the contract terms.",
        sequence_number=1,
    )
    db_session.add(segment)
    await db_session.flush()

    assert meeting.id is not None
    assert segment.meeting_id == meeting.id


@pytest.mark.anyio
async def test_analysis_with_items(db_session: AsyncSession, sample_org_id):
    org = Organization(id=sample_org_id, name="Test Firm")
    matter = Matter(organization_id=sample_org_id, name="Test Matter")
    db_session.add_all([org, matter])
    await db_session.flush()

    meeting = Meeting(
        matter_id=matter.id,
        title="Test Meeting",
        meeting_date=uuid.uuid4(),
    )
    from datetime import UTC
    from datetime import datetime

    meeting.meeting_date = datetime.now(UTC)
    db_session.add(meeting)
    await db_session.flush()

    analysis = Analysis(
        matter_id=matter.id,
        meeting_id=meeting.id,
    )
    db_session.add(analysis)
    await db_session.flush()

    item = AnalysisItem(
        analysis_id=analysis.id,
        item_type="risk",
        title="Data privacy exposure",
        description="Potential GDPR implications identified.",
        severity="high",
    )
    db_session.add(item)
    await db_session.flush()

    assert analysis.id is not None
    assert item.analysis_id == analysis.id


@pytest.mark.anyio
async def test_redline_job_with_changes(db_session: AsyncSession, sample_org_id):
    org = Organization(id=sample_org_id, name="Test Firm")
    matter = Matter(organization_id=sample_org_id, name="Test Matter")
    db_session.add_all([org, matter])
    await db_session.flush()

    doc = Document(
        matter_id=matter.id,
        title="Test Agreement",
        source_filename="agreement.docx",
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        sha256_hash="hash123",
    )
    db_session.add(doc)
    await db_session.flush()

    v1 = DocumentVersion(
        document_id=doc.id,
        version_number=1,
        object_storage_key="docs/v1.docx",
    )
    v2 = DocumentVersion(
        document_id=doc.id,
        version_number=2,
        object_storage_key="docs/v2.docx",
    )
    db_session.add_all([v1, v2])
    await db_session.flush()

    job = RedlineJob(
        matter_id=matter.id,
        base_document_version_id=v1.id,
        comparison_document_version_id=v2.id,
    )
    db_session.add(job)
    await db_session.flush()

    change = RedlineChange(
        redline_job_id=job.id,
        change_type="substitution",
        original_text="Old clause text.",
        proposed_text="New proposed clause text.",
        rationale="Better liability protection.",
    )
    db_session.add(change)
    await db_session.flush()

    assert job.id is not None
    assert change.redline_job_id == job.id


@pytest.mark.anyio
async def test_audit_event(db_session: AsyncSession, sample_org_id, sample_user_id):
    user = User(id=sample_user_id, email="test@example.com", display_name="Test User", organization_id=sample_org_id, hashed_password="hashed")
    org = Organization(id=sample_org_id, name="Test Firm")
    db_session.add_all([org, user])
    await db_session.flush()

    event = AuditEvent(
        organization_id=sample_org_id,
        actor_id=sample_user_id,
        event_type="login",
        resource_type="user",
        resource_id=sample_user_id,
    )
    db_session.add(event)
    await db_session.flush()

    assert event.id is not None
    assert event.organization_id == sample_org_id
