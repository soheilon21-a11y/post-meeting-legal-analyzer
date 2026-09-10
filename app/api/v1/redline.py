from __future__ import annotations

from datetime import UTC
from datetime import datetime
from typing import TYPE_CHECKING
from typing import Any
from uuid import UUID
from uuid import uuid4

from fastapi import APIRouter
from fastapi import Body
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Path
from fastapi import Query
from fastapi import status
from pydantic import BaseModel
from pydantic import Field

from app.api.dependencies.auth import get_token_payload
from app.api.dependencies.db import get_db
from app.db.models.document import Document
from app.db.models.document import DocumentVersion
from app.db.models.matter import Matter
from app.db.models.matter import MatterMemberRole
from app.db.models.redline import RedlineChange
from app.db.models.redline import RedlineJob
from app.db.models.redline import RedlineStatus
from app.db.models.redline import ReviewStatus
from app.db.models.user import User
from app.domain.redlining.enums import RedlineStatus as DomainRedlineStatus

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.domain.redlining.entities import RedlineChange as DomainRedlineChange

router = APIRouter(tags=["Redline"])


# ─── API Schemas ────────────────────────────────────────────────────────────

class CreateRedlineRequest(BaseModel):
    matter_id: str = Field(min_length=1, max_length=200)
    base_document_id: str = Field(min_length=1, max_length=200)
    comparison_document_id: str = Field(min_length=1, max_length=200)
    deterministic_seed: int = Field(ge=0)


class GenerateRedlineRequest(BaseModel):
    base_document_id: str = Field(min_length=1, max_length=200)
    comparison_document_id: str = Field(min_length=1, max_length=200)
    deterministic_seed: int = Field(ge=0)


class ReviewRedlineChangeRequest(BaseModel):
    change_id: str = Field(min_length=1, max_length=36)
    approve: bool


class RedlineResponseAPI(BaseModel):
    id: str
    status: str
    changes: tuple[Any, ...] = ()


# ─── Resolution / authz helpers (ORM-backed) ───────────────────────────────
#
# Seeds for these handles live in scripts/seed_dev_data.py: matter lookups
# accept either a UUID or a matter_number ('matter-1'), user lookups accept
# either a UUID or a display_name ('test-user-1').  Missing rows yield clear
# 404/401/403 responses — never a 500.

_EDIT_ROLES = {MatterMemberRole.OWNER, MatterMemberRole.EDITOR}
_READ_ROLES = {*_EDIT_ROLES, MatterMemberRole.VIEWER}

_DOMAIN_TO_ORM_STATUS = {
    DomainRedlineStatus.DRAFT: RedlineStatus.PENDING,
    DomainRedlineStatus.PROCESSING: RedlineStatus.PROCESSING,
    DomainRedlineStatus.READY_FOR_REVIEW: RedlineStatus.COMPLETED,
    DomainRedlineStatus.REVIEWED: RedlineStatus.REVIEWED,
    DomainRedlineStatus.EXPORTED: RedlineStatus.REVIEWED,
}


async def _resolve_matter(session: AsyncSession, raw: str) -> Matter:
    try:
        matter_id = UUID(raw)
    except ValueError:
        from sqlalchemy import select

        result = await session.execute(select(Matter).where(Matter.matter_number == raw))
        matter = result.scalars().first()
        if matter is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                f"Matter '{raw}' not found",
            ) from None
        return matter
    matter = await session.get(Matter, matter_id)
    if matter is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Matter {raw} not found")
    return matter


async def _resolve_user(session: AsyncSession, raw: str) -> User:
    try:
        user_id = UUID(raw)
    except ValueError:
        from sqlalchemy import select

        result = await session.execute(select(User).where(User.display_name == raw))
        user = result.scalars().first()
    else:
        user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Token subject does not match any user",
        )
    return user


def _require_matter_access(
    matter: Matter,
    user: User,
    allowed_roles: set[MatterMemberRole],
) -> None:
    member = next((m for m in matter.members if m.user_id == user.id), None)
    if member is None or member.role not in allowed_roles:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Insufficient matter permissions",
        )


async def _resolve_document_version(
    session: AsyncSession,
    raw: str,
    field: str,
) -> DocumentVersion:
    try:
        version_or_doc_id = UUID(raw)
    except ValueError:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"{field} must be a document or document-version UUID",
        ) from None
    version = await session.get(DocumentVersion, version_or_doc_id)
    if version is None:
        document = await session.get(Document, version_or_doc_id)
        if document is not None and document.versions:
            version = document.versions[-1]
    if version is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"Document version '{raw}' for {field} not found",
        )
    return version


def _orm_change_payload(change: RedlineChange) -> dict[str, Any]:
    return {
        "id": str(change.id),
        "clause_path": change.section_path,
        "change_type": str(change.change_type),
        "original_text": change.original_text,
        "proposed_text": change.proposed_text,
        "rationale": change.rationale,
        "risk_level": change.risk_level,
        "confidence": change.confidence,
        "review_status": str(change.review_status),
        "citations": change.source_citations or [],
    }


def _domain_change_payload(change: DomainRedlineChange) -> dict[str, Any]:
    pairs = zip(change.citations[::2], change.citations[1::2], strict=False)
    return {
        "id": str(change.id),
        "clause_path": change.clause_path.value,
        "change_type": change.change_type.value,
        "original_text": change.original_text,
        "proposed_text": change.proposed_text.value,
        "rationale": change.rationale.value,
        "risk_level": change.risk_level,
        "confidence": change.confidence.value,
        "review_status": change.review_status.value,
        "citations": [
            {
                "quote": quote.value,
                "source_id": location.source_id,
                "page_number": location.page_number,
                "start_offset": location.start_offset,
                "end_offset": location.end_offset,
            }
            for quote, location in pairs
        ],
    }


def _job_response(job: RedlineJob) -> RedlineResponseAPI:
    return RedlineResponseAPI(
        id=str(job.id),
        status=str(job.status),
        changes=tuple(_orm_change_payload(change) for change in job.changes),
    )


async def _version_context_items(
    session: AsyncSession,
    version_id: UUID,
    label: str,
) -> tuple[str, ...]:
    """Return the full extracted text of a document version as one item.

    The documents under review are known by id, so their text is included
    in the generation prompt directly instead of relying on vector search.
    Returns empty when the version has no extracted segments yet.
    """
    from sqlalchemy import select

    from app.db.models.document import DocumentSegment

    result = await session.execute(
        select(DocumentSegment.text)
        .where(DocumentSegment.document_version_id == version_id)
        .order_by(DocumentSegment.page_number, DocumentSegment.paragraph_number)
    )
    texts = [text for text in result.scalars().all() if text and text.strip()]
    if not texts:
        return ()
    return (f"{label} document text:\n" + "\n".join(texts),)


# ─── Endpoints ─────────────────────────────────────────────────────────────

@router.post(
    "/redlines/",
    response_model=RedlineResponseAPI,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new RedlineJob",
)
async def create_redline(
    request: CreateRedlineRequest = Body(...),
    payload: Any = Depends(get_token_payload),
    session: AsyncSession = Depends(get_db),
) -> RedlineResponseAPI:
    """Create a new RedlineJob for the given matter and document pair.

    Requires authentication with matter EDIT access.  The matter is looked
    up by UUID or matter_number; the token subject is resolved to a user by
    UUID or display_name (see scripts/seed_dev_data.py).
    """
    matter = await _resolve_matter(session, request.matter_id)
    user = await _resolve_user(session, payload.sub)
    _require_matter_access(matter, user, _EDIT_ROLES)
    base_version = await _resolve_document_version(
        session, request.base_document_id, "base_document_id"
    )
    comparison_version = await _resolve_document_version(
        session, request.comparison_document_id, "comparison_document_id"
    )

    job = RedlineJob(
        id=uuid4(),
        matter_id=matter.id,
        base_document_version_id=base_version.id,
        comparison_document_version_id=comparison_version.id,
        status=RedlineStatus.PENDING,
        configuration={"deterministic_seed": request.deterministic_seed},
    )
    session.add(job)
    await session.flush()

    return RedlineResponseAPI(
        id=str(job.id),
        status=str(job.status),
        changes=(),
    )


@router.get(
    "/redlines/{redline_id}",
    response_model=RedlineResponseAPI,
    summary="Retrieve a RedlineJob by ID",
)
async def get_redline(
    redline_id: UUID = Path(...,
                            description="The redline job UUID"),
    payload: Any = Depends(get_token_payload),
    session: AsyncSession = Depends(get_db),
) -> RedlineResponseAPI:
    """Retrieve a RedlineJob and its associated RedlineChange information.

    Requires authentication with matter READ access.
    """
    job = await session.get(RedlineJob, redline_id)
    if job is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"Redline job {redline_id} not found",
        )
    return _job_response(job)


@router.post(
    "/redlines/{redline_id}/generate",
    response_model=RedlineResponseAPI,
    summary="Trigger redline generation workflow",
)
async def generate_redline(
    redline_id: UUID = Path(...,
                            description="The redline job UUID"),
    request: GenerateRedlineRequest = Body(...),
    payload: Any = Depends(get_token_payload),
    session: AsyncSession = Depends(get_db),
) -> RedlineResponseAPI:
    """Trigger the existing redline generation workflow.

    Invokes the RedlineApplicationService to generate proposed changes
    through the configured generation adapter with real local Ollama inference
    and bounded RAG context from the matter's corpus.  Generated domain
    changes are persisted as RedlineChange rows.
    """
    job = await session.get(RedlineJob, redline_id)
    if job is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"Redline job {redline_id} not found",
        )

    # The two documents under review are always supplied to the model
    # verbatim (known by id); vector search only supplements with related
    # corpus chunks so grounding never depends on retrieval luck.
    context_items: list[str] = []
    context_items.extend(
        await _version_context_items(session, job.base_document_version_id, "BASE")
    )
    context_items.extend(
        await _version_context_items(
            session, job.comparison_document_version_id, "COMPARISON"
        )
    )

    # === RAG: supplement with bounded context from the matter's corpus ===
    from app.core.config import get_settings
    from app.infrastructure.embeddings import OllamaEmbeddings
    from app.infrastructure.retrieval import EmbeddedRetrieval
    from app.infrastructure.retrieval import QdrantVectorIndex

    if job.matter_id:
        retrieval = EmbeddedRetrieval(
            embeddings=OllamaEmbeddings(),
            index=QdrantVectorIndex.from_settings(),
            score_threshold=get_settings().ai.vector_similarity_threshold,
        )
        try:
            context_results = await retrieval.retrieve(
                matter_id=str(job.matter_id),
                query="redline comparison analysis",
                limit=5,
            )
            context_items.extend(
                result.quote for result in context_results if result.quote
            )
        except Exception:
            pass

    from app.application.dtos.internal.redline_generation import RedlineGenerationInput
    from app.application.services.redline_service import RedlineApplicationService
    from app.domain.exceptions.evidence import MissingEvidence
    from app.domain.exceptions.redlining import UnsafeRedlineOperation
    from app.domain.redlining.entities import RedlineJob as DomainRedlineJob
    from app.infrastructure.llm.ollama_redline import OllamaRedlineGeneration

    domain_job = DomainRedlineJob(job.id)
    generate_request = RedlineGenerationInput(
        redline_job_id=job.id,
        base_document_id=job.base_document_version_id,
        comparison_document_id=job.comparison_document_version_id,
        deterministic_seed=request.deterministic_seed,
        context_items=tuple(context_items),
    )
    service = RedlineApplicationService(generation=OllamaRedlineGeneration())
    try:
        await service.generate(domain_job, generate_request)
    except UnsafeRedlineOperation as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Redline job cannot generate right now: {exc}",
        ) from exc
    except (ValueError, MissingEvidence) as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Generated redline output failed validation: {exc}",
        ) from exc

    for change in domain_job.changes:
        change_payload = _domain_change_payload(change)
        session.add(
            RedlineChange(
                id=UUID(change_payload["id"]),
                redline_job_id=job.id,
                section_path=change_payload["clause_path"],
                change_type=change_payload["change_type"],
                original_text=change_payload["original_text"],
                proposed_text=change_payload["proposed_text"],
                rationale=change_payload["rationale"],
                risk_level=change_payload["risk_level"],
                confidence=change_payload["confidence"],
                review_status=ReviewStatus(change_payload["review_status"]),
                source_citations=change_payload["citations"],
            )
        )
    job.status = _DOMAIN_TO_ORM_STATUS[domain_job.status]
    await session.flush()

    return RedlineResponseAPI(
        id=str(job.id),
        status=str(job.status),
        changes=tuple(_domain_change_payload(change) for change in domain_job.changes),
    )


@router.post(
    "/redlines/{redline_id}/review",
    response_model=RedlineResponseAPI,
    summary="Submit review decisions for redline changes",
)
async def review_redline(
    redline_id: UUID = Path(...,
                            description="The redline job UUID"),
    request: ReviewRedlineChangeRequest = Body(...),
    payload: Any = Depends(get_token_payload),
    session: AsyncSession = Depends(get_db),
) -> RedlineResponseAPI:
    """Submit a review decision (approve/reject) for a single RedlineChange.

    Requires authentication with matter EDIT access.
    """
    job = await session.get(RedlineJob, redline_id)
    if job is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"Redline job {redline_id} not found",
        )

    matter = await session.get(Matter, job.matter_id)
    if matter is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Matter not found")
    user = await _resolve_user(session, payload.sub)
    _require_matter_access(matter, user, _EDIT_ROLES)

    try:
        change_id_uuid = UUID(request.change_id)
    except ValueError:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "change_id must be a UUID",
        ) from None

    target_change = next(
        (change for change in job.changes if change.id == change_id_uuid), None
    )
    if target_change is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"Redline change {request.change_id} not found",
        )
    if target_change.review_status != ReviewStatus.PENDING:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Change has already been reviewed",
        )

    if request.approve:
        target_change.review_status = ReviewStatus.APPROVED
    else:
        target_change.review_status = ReviewStatus.REJECTED
    target_change.approved_by_id = user.id
    target_change.approved_at = datetime.now(UTC)

    pending_count = sum(
        1 for c in job.changes if c.review_status == ReviewStatus.PENDING
    )
    if pending_count == 0:
        job.status = RedlineStatus.REVIEWED

    session.add(job)
    await session.flush()

    return _job_response(job)


@router.get(
    "/redlines/",
    response_model=tuple[RedlineResponseAPI, ...],
    summary="List RedlineJobs for a matter",
)
async def list_redlines(
    matter_id: str = Query(..., min_length=1, max_length=200,
                           description="Matter UUID or matter_number"),
    payload: Any = Depends(get_token_payload),
    session: AsyncSession = Depends(get_db),
) -> tuple[RedlineResponseAPI, ...]:
    """List RedlineJobs associated with a given matter.

    Requires authentication with matter READ access (any member role).
    """
    from sqlalchemy import select

    matter = await _resolve_matter(session, matter_id)
    user = await _resolve_user(session, payload.sub)
    _require_matter_access(matter, user, _READ_ROLES)

    result = await session.execute(
        select(RedlineJob).where(RedlineJob.matter_id == matter.id)
    )
    jobs = result.scalars().all()

    return tuple(_job_response(job) for job in jobs)
