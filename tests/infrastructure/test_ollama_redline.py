from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest

from app.application.dtos.internal.redline_generation import RedlineGenerationInput
from app.application.exceptions.processing import ProcessingError
from app.infrastructure.llm.ollama_redline import OllamaRedlineGeneration

CONTEXT = "COMPARISON document text:\nPayment is due within 45 days of invoice receipt."
GROUNDED_QUOTE = "Payment is due within 45 days of invoice receipt."


class FakeOllamaClient:
    def __init__(self, response_content: str) -> None:
        self._response_content = response_content
        self.calls: list[dict[str, Any]] = []

    def chat(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        return {"message": {"content": self._response_content}}


def _change_json(quote: str) -> str:
    import json

    return json.dumps(
        {
            "changes": [
                {
                    "clause_path": "Section 4. Payment",
                    "change_type": "substitution",
                    "original_text": GROUNDED_QUOTE,
                    "proposed_text": "Payment is due within 30 days of invoice receipt.",
                    "rationale": "Shortens the payment window.",
                    "risk_level": "medium",
                    "confidence": 0.8,
                    "citations": [
                        {
                            "source_id": "COMPARISON document",
                            "quote": quote,
                        }
                    ],
                }
            ]
        }
    )


def _adapter_with(content: str) -> tuple[OllamaRedlineGeneration, FakeOllamaClient]:
    fake = FakeOllamaClient(content)
    adapter = OllamaRedlineGeneration(model_name="test-model", base_url="http://test")
    adapter._client = fake  # type: ignore[attr-defined]
    return adapter, fake


def _request() -> RedlineGenerationInput:
    return RedlineGenerationInput(
        redline_job_id=uuid4(),
        base_document_id=uuid4(),
        comparison_document_id=uuid4(),
        deterministic_seed=42,
        context_items=(CONTEXT,),
    )


@pytest.mark.anyio
async def test_verbatim_ground_quote_passes_validation() -> None:
    adapter, fake = _adapter_with(_change_json(GROUNDED_QUOTE))

    result = await adapter.generate(_request())

    assert len(result.changes) == 1
    assert result.changes[0].citations[0].quote == GROUNDED_QUOTE
    prompt = fake.calls[0]["messages"][0]["content"]
    assert CONTEXT in prompt
    assert "no paraphrasing, no re-casing" in prompt


@pytest.mark.anyio
async def test_paraphrased_quote_is_rejected_as_not_grounded() -> None:
    adapter, _ = _adapter_with(
        _change_json("Payment must be made within about forty-five days.")
    )

    with pytest.raises(ProcessingError, match="not grounded"):
        await adapter.generate(_request())
