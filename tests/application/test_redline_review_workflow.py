from __future__ import annotations

from uuid import uuid4

import pytest

from app.application.dtos.internal.redline_generation import GeneratedRedlineChange
from app.application.dtos.internal.redline_generation import GeneratedRedlineCitation
from app.application.dtos.internal.redline_generation import RedlineGenerationInput
from app.application.dtos.internal.redline_generation import RedlineGenerationResult
from app.application.exceptions.not_found import ResourceNotFound
from app.application.ports.redline_generation import RedlineGenerationPort
from app.application.services.redline_service import RedlineApplicationService
from app.application.workflows.redline_review import RedlineReviewWorkflow
from app.domain.exceptions.redlining import UnsafeRedlineOperation
from app.domain.redlining.entities import RedlineJob
from app.domain.redlining.enums import RedlineStatus
from app.domain.shared.identifiers import RedlineJobId


class FakeRedlineGeneration(RedlineGenerationPort):
    def __init__(self, result: RedlineGenerationResult) -> None:
        self._result = result

    async def generate(self, request: RedlineGenerationInput) -> RedlineGenerationResult:
        return self._result


def _result(*, with_change: bool = True) -> RedlineGenerationResult:
    if not with_change:
        return RedlineGenerationResult(changes=())
    return RedlineGenerationResult(
        changes=(
            GeneratedRedlineChange(
                clause_path="4.2 Liability",
                change_type="substitution",
                original_text="The supplier is liable.",
                proposed_text="The supplier is liable for direct losses only.",
                rationale="Limits exposure to direct losses.",
                risk_level="high",
                confidence=0.91,
                citations=(GeneratedRedlineCitation("contract-v1", "The supplier is liable."),),
            ),
        )
    )


def _request(job: RedlineJob) -> RedlineGenerationInput:
    return RedlineGenerationInput(
        redline_job_id=job.id,
        base_document_id=uuid4(),
        comparison_document_id=uuid4(),
        deterministic_seed=1,
    )


def _workflow(with_change: bool = True) -> RedlineReviewWorkflow:
    return RedlineReviewWorkflow(
        RedlineApplicationService(FakeRedlineGeneration(_result(with_change=with_change)))
    )


async def _prepared_job() -> tuple[RedlineJob, RedlineReviewWorkflow]:
    job = RedlineJob(RedlineJobId(uuid4()))
    workflow = _workflow()
    await workflow.prepare(job, _request(job))
    return job, workflow


async def test_prepare_leaves_job_ready_for_review() -> None:
    job, workflow = await _prepared_job()

    assert job.status is RedlineStatus.READY_FOR_REVIEW
    assert len(job.changes) == 1


async def test_full_review_cycle_approves_reviews_and_exports() -> None:
    job, workflow = await _prepared_job()

    workflow.decide(job, str(job.changes[0].id), approve=True)
    assert workflow.progress(job).is_complete

    workflow.finalize(job)
    assert job.status is RedlineStatus.REVIEWED

    workflow.publish(job)
    assert job.status is RedlineStatus.EXPORTED


async def test_finalize_requires_all_changes_decided() -> None:
    job, workflow = await _prepared_job()

    with pytest.raises(UnsafeRedlineOperation, match="pending changes remain"):
        workflow.finalize(job)


async def test_finalize_requires_at_least_one_change() -> None:
    job = RedlineJob(RedlineJobId(uuid4()))
    workflow = _workflow(with_change=False)
    await workflow.prepare(job, _request(job))

    with pytest.raises(UnsafeRedlineOperation, match="at least one proposed change"):
        workflow.finalize(job)


async def test_decide_unknown_change_raises_not_found() -> None:
    job, workflow = await _prepared_job()

    with pytest.raises(ResourceNotFound):
        workflow.decide(job, str(uuid4()), approve=True)


async def test_decide_malformed_change_id_raises_not_found() -> None:
    job, workflow = await _prepared_job()

    with pytest.raises(ResourceNotFound):
        workflow.decide(job, "not-a-uuid", approve=True)


async def test_progress_counts_decisions() -> None:
    job, workflow = await _prepared_job()

    workflow.decide(job, str(job.changes[0].id), approve=False)
    progress = workflow.progress(job)

    assert progress.total == 1
    assert progress.approved == 0
    assert progress.rejected == 1
    assert progress.pending == 0


async def test_decide_rejected_change_cannot_be_approved_again() -> None:
    job, workflow = await _prepared_job()
    workflow.decide(job, str(job.changes[0].id), approve=False)

    with pytest.raises(UnsafeRedlineOperation, match="already been reviewed"):
        workflow.decide(job, str(job.changes[0].id), approve=True)
