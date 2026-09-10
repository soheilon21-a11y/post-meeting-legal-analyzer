from __future__ import annotations

from datetime import date
from typing import Any
from uuid import uuid4

import pytest

from app.application.dtos.internal.analysis_generation import AnalysisGenerationInput
from app.application.dtos.internal.analysis_generation import AnalysisGenerationResult
from app.application.dtos.internal.analysis_generation import EvidenceInput
from app.application.exceptions.processing import ProcessingError
from app.infrastructure.llm.ollama_analysis import OllamaAnalysisGeneration


class FakeOllamaClient:
    """Deterministic fake Ollama client for unit tests."""

    def __init__(self, response_content: str) -> None:
        self._response_content = response_content
        self.calls: list[dict[str, Any]] = []

    def chat(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        return {"message": {"content": self._response_content}}


@pytest.fixture
def valid_json_response() -> str:
    return """{
  "summary": "The parties discussed liability wording.",
  "risks": [
    {
      "title": "Liability wording",
      "description": "Current wording may expose supplier to unlimited liability.",
      "level": "high",
      "confidence": 0.92,
      "evidence": [
        {"source_id": "transcript", "quote": "The supplier is liable for all damages."}
      ]
    }
  ],
  "obligations": [
    {
      "title": "Review liability clause",
      "description": "Counsel must review the liability clause before next meeting.",
      "responsible_party": "Counsel",
      "confidence": 0.85,
      "evidence": [
        {"source_id": "transcript", "quote": "We agreed to review liability."}
      ],
      "due_date": "2026-10-15"
    }
  ],
  "action_items": [
    {
      "title": "Prepare revised wording",
      "description": "Draft revised liability wording.",
      "responsible_party": "Counsel",
      "confidence": 0.80,
      "evidence": [
        {"source_id": "transcript", "quote": "Prepare the revision."}
      ],
      "due_date": null
    }
  ]
}"""


@pytest.mark.anyio
async def test_adapter_produces_analysis_generation_result(valid_json_response: str) -> None:
    adapter = OllamaAnalysisGeneration(model_name="test-model", base_url="http://test")
    adapter._client = FakeOllamaClient(valid_json_response)  # type: ignore[attr-defined]

    request = AnalysisGenerationInput(
        analysis_id=uuid4(),
        meeting_id=uuid4(),
        transcript=(
            "The supplier is liable for all damages. We agreed to review liability. "
            "Prepare the revision."
        ),
        evidence=(),
        analysis_type="full_meeting",
    )

    result = await adapter.generate(request)

    assert isinstance(result, AnalysisGenerationResult)
    assert result.summary == "The parties discussed liability wording."
    assert len(result.risks) == 1
    assert result.risks[0].title == "Liability wording"
    assert result.risks[0].level == "high"
    assert result.risks[0].confidence == 0.92
    assert len(result.risks[0].evidence) == 1
    assert result.risks[0].evidence[0].quote == "The supplier is liable for all damages."

    assert len(result.obligations) == 1
    assert result.obligations[0].title == "Review liability clause"
    assert result.obligations[0].due_date == date(2026, 10, 15)

    assert len(result.action_items) == 1
    assert result.action_items[0].title == "Prepare revised wording"
    assert result.action_items[0].due_date is None


@pytest.mark.anyio
async def test_adapter_passes_model_and_messages_to_client(valid_json_response: str) -> None:
    fake = FakeOllamaClient(valid_json_response)
    adapter = OllamaAnalysisGeneration(model_name="demo-model", base_url="http://demo:11434")
    adapter._client = fake  # type: ignore[attr-defined]

    request = AnalysisGenerationInput(
        analysis_id=uuid4(),
        meeting_id=uuid4(),
        transcript="Hello world.",
        evidence=(),
        analysis_type="full_meeting",
    )
    await adapter.generate(request)

    assert len(fake.calls) == 1
    call = fake.calls[0]
    assert call["model"] == "demo-model"
    assert call["format"] == "json"
    messages = call["messages"]
    assert len(messages) == 1
    assert messages[0]["role"] == "user"
    assert "Hello world." in messages[0]["content"]


@pytest.mark.anyio
async def test_adapter_raises_processing_error_on_invalid_json() -> None:
    adapter = OllamaAnalysisGeneration()
    adapter._client = FakeOllamaClient("not json")  # type: ignore[attr-defined]

    request = AnalysisGenerationInput(
        analysis_id=uuid4(),
        meeting_id=uuid4(),
        transcript="x",
        evidence=(),
        analysis_type="full_meeting",
    )

    with pytest.raises(ProcessingError, match="not valid JSON"):
        await adapter.generate(request)


@pytest.mark.anyio
async def test_adapter_raises_processing_error_on_empty_response() -> None:
    adapter = OllamaAnalysisGeneration()
    adapter._client = FakeOllamaClient("")  # type: ignore[attr-defined]

    request = AnalysisGenerationInput(
        analysis_id=uuid4(),
        meeting_id=uuid4(),
        transcript="x",
        evidence=(),
        analysis_type="full_meeting",
    )

    with pytest.raises(ProcessingError, match="empty content"):
        await adapter.generate(request)


@pytest.mark.anyio
async def test_adapter_adds_fallback_evidence_when_risk_has_none() -> None:
    json_text = """{
  "summary": "Test.",
  "risks": [
    {
      "title": "No-evidence risk",
      "description": "Desc",
      "level": "high",
      "confidence": 0.9,
      "evidence": []
    }
  ],
  "obligations": [],
  "action_items": []
}"""
    adapter = OllamaAnalysisGeneration()
    adapter._client = FakeOllamaClient(json_text)  # type: ignore[attr-defined]

    request = AnalysisGenerationInput(
        analysis_id=uuid4(),
        meeting_id=uuid4(),
        transcript="x",
        evidence=(),
        analysis_type="full_meeting",
    )
    result = await adapter.generate(request)
    assert len(result.risks[0].evidence) == 1
    assert result.risks[0].evidence[0].source_id == "transcript"


@pytest.mark.anyio
async def test_prompt_labels_corpus_evidence_with_source_id() -> None:
    fake = FakeOllamaClient(
        '{"summary": "Test.", "risks": [], "obligations": [], "action_items": []}'
    )
    adapter = OllamaAnalysisGeneration(model_name="test-model", base_url="http://test")
    adapter._client = fake  # type: ignore[attr-defined]

    request = AnalysisGenerationInput(
        analysis_id=uuid4(),
        meeting_id=uuid4(),
        transcript="We discussed payment terms.",
        evidence=(
            EvidenceInput("contract-1", "Payment terms were changed to 45 days."),
        ),
        analysis_type="full_meeting",
    )
    await adapter.generate(request)

    prompt = fake.calls[0]["messages"][0]["content"]
    assert "[Source: contract-1] Payment terms were changed to 45 days." in prompt
    assert '"contract-1"' in prompt


@pytest.mark.anyio
async def test_corpus_source_id_citation_is_kept_and_invented_id_dropped() -> None:
    json_text = """{
  "summary": "Payment window extended.",
  "risks": [
    {
      "title": "Payment term mismatch",
      "description": "Transcript says 30 days but contract says 45.",
      "level": "medium",
      "confidence": 0.9,
      "evidence": [
        {"source_id": "transcript", "quote": "Payment is due in 30 days."},
        {"source_id": "contract-1", "quote": "Payment terms were changed to 45 days."},
        {"source_id": "additional_evidence", "quote": "invented"}
      ]
    }
  ],
  "obligations": [],
  "action_items": []
}"""
    adapter = OllamaAnalysisGeneration(model_name="test-model", base_url="http://test")
    adapter._client = FakeOllamaClient(json_text)  # type: ignore[attr-defined]

    request = AnalysisGenerationInput(
        analysis_id=uuid4(),
        meeting_id=uuid4(),
        transcript="Payment is due in 30 days.",
        evidence=(
            EvidenceInput("contract-1", "Payment terms were changed to 45 days."),
        ),
        analysis_type="full_meeting",
    )
    result = await adapter.generate(request)

    source_ids = {e.source_id for e in result.risks[0].evidence}
    assert source_ids == {"transcript", "contract-1"}
    assert "additional_evidence" not in source_ids
