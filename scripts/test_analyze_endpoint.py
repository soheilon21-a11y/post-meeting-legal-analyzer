"""Quick integration sanity check for the /analyze endpoint."""

from __future__ import annotations

import asyncio
from uuid import uuid4

from app.api.v1.analyses import analyze, AnalyzeRequest


async def test_fallback_when_ollama_fails() -> None:
    """Simulate an Ollama failure and verify the endpoint falls back to
    rule-based analysis and still returns HTTP 200 equivalent data."""
    request = AnalyzeRequest(
        text="The supplier is liable for all damages. Counsel must review the clause.",
        use_llm=True,
        model="nonexistent-model-12345",
    )
    response = await analyze(request)
    assert response.status == "ready_for_review"
    assert response.summary != ""
    # Rule-based scanner should find liability and must
    item_types = {item.item_type for item in response.items}
    assert "risk" in item_types or "obligation" in item_types
    print("Fallback test passed:", response.summary, item_types)


async def test_rule_based_direct() -> None:
    request = AnalyzeRequest(
        text="Alice agreed to prepare the revised wording by Friday. Bob is responsible for the review.",
        use_llm=False,
    )
    response = await analyze(request)
    assert response.status == "ready_for_review"
    item_types = {item.item_type for item in response.items}
    assert "action_item" in item_types or "obligation" in item_types
    print("Rule-based direct test passed:", response.summary, item_types)


if __name__ == "__main__":
    asyncio.run(test_fallback_when_ollama_fails())
    asyncio.run(test_rule_based_direct())
