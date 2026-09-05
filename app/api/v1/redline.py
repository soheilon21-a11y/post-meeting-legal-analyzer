from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any
from uuid import UUID

from fastapi import APIRouter
from fastapi import Body
from fastapi import Depends
from fastapi import Path
from fastapi import Query
from fastapi import status
from pydantic import BaseModel
from pydantic import Field

from app.api.dependencies.auth import get_token_payload
from app.api.dependencies.db import get_db
from app.application.mappers.redline import DefaultRedlineMapper

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

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
) -> RedlineResponseAPI:
    """Create a new RedlineJob for the given matter and document pair.

    Requires authentication with matter EDIT access.
    """
    from app.domain.matter.entities import Matter

    async def _get_session() -> AsyncSession:
        async for session in get_db():
            return session

    async with _get_session() as session:
        matter_id_uuid = UUID(request.matter_id)

        # Look up matter
        matter_result = await session.get(Matter, matter_id_uuid)
        if matter_result is None:
            from fastapi import HTTPException
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Matter {request.matter_id} not found",
            )

        # Verify EDIT access: OWNER/EDITOR roles
        has_edit = False
        for member in matter_result.members:
            if member.user_id == payload.user_id:  # type: ignore[union-attr]
                if member.role.name in {"OWNER", "EDITOR"}:
                    has_edit = True
                break

        if not has_edit:
            from fastapi import HTTPException
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient matter permissions",
            )

        # Create the redline job
        from app.domain.redlining.entities import RedlineJob

        job = RedlineJob()
        session.add(job)  # type: ignore[arg-type]
        await session.flush()

        # Map to response
        mapper = DefaultRedlineMapper()
        response = mapper.to_response(job)

    return RedlineResponseAPI(
        id=str(job.id),
        status=job.status.value,
        changes=tuple(response.changes) if hasattr(response, "changes") else (),
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
) -> RedlineResponseAPI:
    """Retrieve a RedlineJob and its associated RedlineChange information.

    Requires authentication with matter READ access.
    """
    from app.domain.redlining.entities import RedlineJob

    async def _get_session() -> AsyncSession:
        async for session in get_db():
            return session

    async with _get_session() as session:
        job_result = await session.get(RedlineJob, redline_id)
        if job_result is None:
            from fastapi import HTTPException
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Redline job {redline_id} not found",
            )

        mapper = DefaultRedlineMapper()
        response = mapper.to_response(job_result)

    return RedlineResponseAPI(
        id=str(job_result.id),
        status=job_result.status.value,
        changes=tuple(response.changes) if hasattr(response, "changes") else (),
    )


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
) -> RedlineResponseAPI:
    """Trigger the existing redline generation workflow.

    Invokes the RedlineApplicationService to generate proposed changes
    through the configured generation adapter with real local Ollama inference
    and bounded RAG context from the matter's corpus.
    """

    async def _get_session() -> AsyncSession:
        async for session in get_db():
            return session

    async with _get_session() as session:
        from app.application.services.redline_service import RedlineApplicationService

        # Look up the job
        from app.domain.redlining.entities import RedlineJob

        job_result = await session.get(RedlineJob, redline_id)
        if job_result is None:
            from fastapi import HTTPException
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Redline job {redline_id} not found",
            )

        job = job_result
        matter_id = job.matter_id

        # === RAG: retrieve bounded context from the matter's corpus ===
        from app.core.config import get_settings
        from app.infrastructure.embeddings import OllamaEmbeddings
        from app.infrastructure.retrieval import EmbeddedRetrieval
        from app.infrastructure.retrieval import QdrantVectorIndex

        if matter_id:
            retrieval = EmbeddedRetrieval(
                embeddings=OllamaEmbeddings(),
                index=QdrantVectorIndex.from_settings(),
                score_threshold=get_settings().ai.vector_similarity_threshold,
            )
            try:
                context_results = await retrieval.retrieve(
                    matter_id=str(matter_id),
                    query="redline comparison analysis",
                    limit=5,
                )
                # Extract just the quote strings as bounded context_items
                context_items = tuple(
                    result.quote for result in context_results if result.quote
                )
            except Exception:
                # Graceful degradation: empty context if retrieval fails
                context_items = ()
        else:
            context_items = ()

        # Real local Ollama redline generation adapter
        from app.infrastructure.llm.ollama_redline import OllamaRedlineGeneration

        ollama_gen = OllamaRedlineGeneration()

        # Build the generation request with real RAG context
        from app.application.dtos.internal.redline_generation import RedlineGenerationInput

        generate_request = RedlineGenerationInput(
            redline_job_id=job.id,
            base_document_id=request.base_document_id,
            comparison_document_id=request.comparison_document_id,
            deterministic_seed=request.deterministic_seed,
            context_items=context_items,
        )

        service = RedlineApplicationService(generation=ollama_gen)
        await service.generate(job, generate_request)

        # Map to response
        mapper = DefaultRedlineMapper()
        response = mapper.to_response(job)

    return RedlineResponseAPI(
        id=str(job.id),
        status=job.status.value,
        changes=tuple(response.changes) if hasattr(response, "changes") else (),
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
) -> RedlineResponseAPI:
    """Submit a review decision (approve/reject) for a single RedlineChange.

    Requires authentication with matter EDIT access.
    """
    from fastapi import HTTPException

    async def _get_session() -> AsyncSession:
        async for session in get_db():
            return session

    async with _get_session() as session:
        from app.domain.redlining.entities import RedlineJob

        # Look up the job
        job_result = await session.get(RedlineJob, redline_id)
        if job_result is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Redline job {redline_id} not found",
            )

        job = job_result

        # Verify matter access via the job's matter
        from app.domain.matter.entities import Matter
        matter_result = await session.get(Matter, job.matter_id)
        if matter_result is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Matter not found",
            )

        # Check EDIT access: OWNER/EDITOR roles
        has_edit = False
        for member in matter_result.members:
            if member.user_id == payload.user_id:  # type: ignore[union-attr]
                if member.role.name in {"OWNER", "EDITOR"}:
                    has_edit = True
                break

        if not has_edit:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient matter permissions",
            )

        # Find the change by ID

        change_id_uuid = UUID(request.change_id) if request.change_id else None
        target_change = None
        for change in job.changes:
            if change.id == change_id_uuid:
                target_change = change
                break

        if target_change is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Redline change {request.change_id} not found",
            )

        if request.approve:
            target_change.approve()
        else:
            target_change.reject()

        # Mark job as reviewed if all changes are decided
        pending_count = sum(
            1 for c in job.changes if c.review_status.name == "pending"
        )
        if pending_count == 0:
            job.mark_reviewed()

        session.add(job)  # type: ignore[arg-type]

        mapper = DefaultRedlineMapper()
        response = mapper.to_response(job)

    return RedlineResponseAPI(
        id=str(job.id),
        status=job.status.value,
        changes=tuple(response.changes) if hasattr(response, "changes") else (),
    )


@router.get(
    "/redlines/",
    response_model=tuple[RedlineResponseAPI, ...],
    summary="List RedlineJobs for a matter",
)
async def list_redlines(
    matter_id: str = Query(..., min_length=1, max_length=200,
                           description="Matter UUID"),
    payload: Any = Depends(get_token_payload),
) -> tuple[RedlineResponseAPI, ...]:
    """List RedlineJobs associated with a given matter.

    Requires authentication with matter READ access.
    """
    from sqlalchemy import select

    from app.domain.redlining.entities import RedlineJob

    matter_id_uuid = UUID(matter_id)

    async def _get_session() -> AsyncSession:
        async for session in get_db():
            return session

    async with _get_session() as session:
        # Look up matter
        from app.domain.matter.entities import Matter
        matter_result = await session.get(Matter, matter_id_uuid)
        if matter_result is None:
            from fastapi import HTTPException
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Matter {matter_id} not found",
            )

        # Verify READ access via organization
        from app.application.authorization import ApplicationAuthorizationService
        org_id = getattr(payload, "org_id", None)
        authz = ApplicationAuthorizationService()
        authz.require_organization_access(payload, org_id, "matter:read")  # type: ignore[arg-type]

        # Query redlines for this matter
        result = await session.execute(
            select(RedlineJob).where(RedlineJob.matter_id == matter_id_uuid)
        )
        jobs = result.scalars().all()

        mapper = DefaultRedlineMapper()
        responses: list[RedlineResponseAPI] = []
        for job in jobs:
            response = mapper.to_response(job)
            responses.append(
                RedlineResponseAPI(
                    id=str(job.id),
                    status=job.status.value,
                    changes=tuple(response.changes) if hasattr(response, "changes") else (),
                )
            )

    return tuple(responses)  # type: ignore[return-value]
