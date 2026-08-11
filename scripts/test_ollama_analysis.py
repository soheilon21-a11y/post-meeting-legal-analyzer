"""Manual verification script for the Ollama analysis adapter.

Run this script against a live local Ollama server to verify that the
AnalysisGenerationPort adapter works end-to-end with a real model.

Prerequisites:
  - Ollama is running (default: http://127.0.0.1:11434)
  - A model is pulled (default: llama3.2)

Usage:
  python scripts/test_ollama_analysis.py
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

from app.application.dtos.internal.analysis_generation import AnalysisGenerationInput
from app.infrastructure.llm import OllamaAnalysisGeneration


async def main() -> None:
    adapter = OllamaAnalysisGeneration()
    request = AnalysisGenerationInput(
        analysis_id=uuid4(),
        meeting_id=uuid4(),
        transcript=(
            "Alice: The supplier is liable for all damages including indirect losses.\n"
            "Bob: We should cap liability at the contract value.\n"
            "Alice: Agreed, but counsel must review the wording before we sign.\n"
            "Bob: I'll prepare the revised clause by Friday."
        ),
        evidence=(),
        analysis_type="full_meeting",
    )

    print("Sending request to Ollama...")
    result = await adapter.generate(request)

    print("\n=== SUMMARY ===")
    print(result.summary)

    print("\n=== RISKS ===")
    for risk in result.risks:
        print(f"  - {risk.title} ({risk.level}, confidence={risk.confidence})")
        print(f"    {risk.description}")

    print("\n=== OBLIGATIONS ===")
    for obl in result.obligations:
        print(f"  - {obl.title} (responsible={obl.responsible_party}, confidence={obl.confidence})")
        print(f"    {obl.description}")
        if obl.due_date:
            print(f"    Due: {obl.due_date}")

    print("\n=== ACTION ITEMS ===")
    for item in result.action_items:
        print(f"  - {item.title} (responsible={item.responsible_party}, confidence={item.confidence})")
        print(f"    {item.description}")
        if item.due_date:
            print(f"    Due: {item.due_date}")

    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
