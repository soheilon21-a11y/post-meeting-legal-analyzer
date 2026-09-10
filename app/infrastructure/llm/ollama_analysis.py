from __future__ import annotations

import asyncio
import json
from datetime import date
from datetime import datetime
from typing import Any

from app.application.dtos.internal.analysis_generation import AnalysisGenerationInput
from app.application.dtos.internal.analysis_generation import AnalysisGenerationResult
from app.application.dtos.internal.analysis_generation import EvidenceInput
from app.application.dtos.internal.analysis_generation import GeneratedActionItem
from app.application.dtos.internal.analysis_generation import GeneratedObligation
from app.application.dtos.internal.analysis_generation import GeneratedRisk
from app.application.exceptions.processing import ProcessingError
from app.application.ports.llm_generation import AnalysisGenerationPort
from app.core.config import get_settings


class OllamaAnalysisGeneration(AnalysisGenerationPort):
    """Concrete AnalysisGenerationPort adapter using a local Ollama server."""

    def __init__(
        self,
        model_name: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self._model_name = model_name or get_settings().ollama.default_model
        self._base_url = base_url or get_settings().ollama.base_url
        self._timeout = get_settings().ollama.timeout_seconds
        self._client: Any | None = None

    async def generate(self, request: AnalysisGenerationInput) -> AnalysisGenerationResult:
        try:
            import ollama
        except ImportError as exc:
            raise ProcessingError("analysis_generation", "ollama package is not installed") from exc

        client = self._client or ollama.Client(host=self._base_url, timeout=self._timeout)
        prompt = self._build_prompt(request)

        try:
            response = await asyncio.to_thread(
                client.chat,
                model=self._model_name,
                messages=[{"role": "user", "content": prompt}],
                format="json",
            )
        except Exception as exc:
            raise ProcessingError(
                "analysis_generation",
                f"Ollama chat call failed: {exc}",
            ) from exc

        content = response.get("message", {}).get("content", "")
        if not content:
            raise ProcessingError(
                "analysis_generation",
                "Ollama returned empty content",
            )

        allowed_source_ids = {"transcript"} | {
            e.source_id for e in request.evidence if e.source_id
        }
        return self._parse_result(content, allowed_source_ids)

    def _build_prompt(self, request: AnalysisGenerationInput) -> str:
        evidence_text = ""
        citation_rules = (
            "- Every risk, obligation, and action item must include at least one evidence "
            'entry with a "source_id" and a verbatim "quote".\n'
            '- Cite "transcript" only for statements made in the transcript itself.\n'
        )
        if request.evidence:
            evidence_text = (
                "\n\nRETRIEVED CORPUS EVIDENCE (from indexed matter documents, each labeled "
                "with its source_id):\n"
                + "\n".join(f"[Source: {e.source_id}] {e.quote}" for e in request.evidence)
            )
            corpus_ids = ", ".join(
                f'"{source_id}"'
                for source_id in dict.fromkeys(e.source_id for e in request.evidence)
            )
            citation_rules += (
                "- When a finding is supported by corpus evidence, its evidence entry must "
                "cite the exact source_id of the supporting document. "
                f"Allowed corpus source_ids: {corpus_ids}.\n"
                "- When both the transcript and a corpus document support a finding, "
                "cite both source_ids in separate evidence entries.\n"
                "- Never invent source_ids or reuse section labels as source_ids.\n"
            )

        return (
            "You are a conservative legal analyst. Analyze the following meeting transcript "
            "and produce a JSON response. Do not invent facts. Only report what is present "
            "or reasonably implied in the text.\n\n"
            f"TRANSCRIPT:\n{request.transcript}{evidence_text}\n\n"
            "Produce a JSON object matching this exact structure:\n"
            "{\n"
            '  "summary": "One-paragraph summary of the meeting from a legal perspective.",\n'
            '  "risks": [\n'
            "    {\n"
            '      "title": "Short risk title",\n'
            '      "description": "Detailed description",\n'
            '      "level": "low|medium|high|critical",\n'
            '      "confidence": 0.85,\n'
            '      "evidence": [{"source_id": "transcript or a corpus source_id", '
            '"quote": "relevant quote"}]\n'
            "    },\n"
            "    {\n"
            '      "title": "Liability cap exposes buyer",\n'
            '      "description": "Risk FOR THE CLIENT (the buyer): the contract caps '
            'liability at direct damages, so the client cannot recover consequential '
            'losses.",\n'
            '      "level": "high",\n'
            '      "confidence": 0.9,\n'
            '      "evidence": [{"source_id": "a corpus source_id", "quote": '
            '"relevant quote from the retrieved document"}]\n'
            "    }\n"
            "  ],\n"
            '  "obligations": [\n'
            "    {\n"
            '      "title": "Short obligation title",\n'
            '      "description": "Detailed description",\n'
            '      "responsible_party": "Who is responsible",\n'
            '      "confidence": 0.80,\n'
            '      "evidence": [{"source_id": "transcript or a corpus source_id", '
            '"quote": "relevant quote"}],\n'
            '      "due_date": "YYYY-MM-DD" or null\n'
            "    }\n"
            "  ],\n"
            '  "action_items": [\n'
            "    {\n"
            '      "title": "Short action title",\n'
            '      "description": "Detailed description",\n'
            '      "responsible_party": "Who should act",\n'
            '      "confidence": 0.80,\n'
            '      "evidence": [{"source_id": "transcript or a corpus source_id", '
            '"quote": "relevant quote"}],\n'
            '      "due_date": "YYYY-MM-DD" or null\n'
            "    }\n"
            "  ]\n"
            "}\n\n"
            "Rules:\n"
            '- "level" must be exactly one of: low, medium, high, critical\n'
            '- "confidence" must be a float between 0.0 and 1.0\n'
            f"{citation_rules}"
            "- Analyze the situation from the perspective of the party hosting the meeting "
            "(the client side). Every risk must state whose interest is harmed.\n"
            "- COVERAGE RULE: every distinct topic that any speaker explicitly raised in "
            "the transcript MUST appear in the output — as a risk, obligation, or action "
            "item. If a topic was flagged in the meeting as a concern (e.g. 'we will flag "
            "it as a risk'), it MUST become a risk item, even if the contract is silent on "
            "it. A topic being absent from the contract while discussed in the meeting is "
            "itself reportable.\n"
            "- When the retrieved contract evidence addresses the same topic as the "
            "transcript, state in the description whether the terms match or differ.\n"
            "- If a category has no entries, return an empty array []\n"
            "- Do not wrap the JSON in markdown code fences\n"
            "- Return only raw JSON\n"
        )

    def _parse_result(
        self,
        content: str,
        allowed_source_ids: set[str] | frozenset[str],
    ) -> AnalysisGenerationResult:
        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ProcessingError(
                "analysis_generation",
                f"Model output is not valid JSON: {exc}",
            ) from exc

        summary = data.get("summary", "")
        risks = self._parse_risks(data.get("risks", []), allowed_source_ids)
        obligations = self._parse_obligations(data.get("obligations", []), allowed_source_ids)
        action_items = self._parse_action_items(data.get("action_items", []), allowed_source_ids)

        return AnalysisGenerationResult(
            summary=summary,
            risks=risks,
            obligations=obligations,
            action_items=action_items,
        )

    def _parse_risks(
        self,
        items: list[dict[str, Any]],
        allowed_source_ids: set[str] | frozenset[str],
    ) -> tuple[GeneratedRisk, ...]:
        result: list[GeneratedRisk] = []
        for idx, item in enumerate(items):
            evidence = self._parse_evidence(item.get("evidence", []), allowed_source_ids)
            # Ensure at least one evidence entry so domain invariants are satisfied
            if not evidence:
                evidence = (
                    EvidenceInput(
                        source_id="transcript",
                        quote="Derived from meeting transcript.",
                    ),
                )
            try:
                result.append(
                    GeneratedRisk(
                        title=item.get("title", f"Risk {idx + 1}"),
                        description=item.get("description", ""),
                        level=item.get("level", "medium"),
                        confidence=float(item.get("confidence", 0.5)),
                        evidence=evidence,
                    )
                )
            except (TypeError, ValueError) as exc:
                raise ProcessingError(
                    "analysis_generation",
                    f"Invalid risk item at index {idx}: {exc}",
                ) from exc
        return tuple(result)

    def _parse_obligations(
        self,
        items: list[dict[str, Any]],
        allowed_source_ids: set[str] | frozenset[str],
    ) -> tuple[GeneratedObligation, ...]:
        result: list[GeneratedObligation] = []
        for idx, item in enumerate(items):
            evidence = self._parse_evidence(item.get("evidence", []), allowed_source_ids)
            if not evidence:
                evidence = (
                    EvidenceInput(
                        source_id="transcript",
                        quote="Derived from meeting transcript.",
                    ),
                )
            due_date = self._parse_optional_date(item.get("due_date"))
            try:
                result.append(
                    GeneratedObligation(
                        title=item.get("title", f"Obligation {idx + 1}"),
                        description=item.get("description", ""),
                        responsible_party=item.get("responsible_party", ""),
                        confidence=float(item.get("confidence", 0.5)),
                        evidence=evidence,
                        due_date=due_date,
                    )
                )
            except (TypeError, ValueError) as exc:
                raise ProcessingError(
                    "analysis_generation",
                    f"Invalid obligation item at index {idx}: {exc}",
                ) from exc
        return tuple(result)

    def _parse_action_items(
        self,
        items: list[dict[str, Any]],
        allowed_source_ids: set[str] | frozenset[str],
    ) -> tuple[GeneratedActionItem, ...]:
        result: list[GeneratedActionItem] = []
        for idx, item in enumerate(items):
            evidence = self._parse_evidence(item.get("evidence", []), allowed_source_ids)
            due_date = self._parse_optional_date(item.get("due_date"))
            try:
                result.append(
                    GeneratedActionItem(
                        title=item.get("title", f"Action Item {idx + 1}"),
                        description=item.get("description", ""),
                        responsible_party=item.get("responsible_party", ""),
                        confidence=float(item.get("confidence", 0.5)),
                        evidence=evidence,
                        due_date=due_date,
                    )
                )
            except (TypeError, ValueError) as exc:
                raise ProcessingError(
                    "analysis_generation",
                    f"Invalid action item at index {idx}: {exc}",
                ) from exc
        return tuple(result)

    @staticmethod
    def _parse_evidence(
        items: list[dict[str, Any]],
        allowed_source_ids: set[str] | frozenset[str],
    ) -> tuple[EvidenceInput, ...]:
        result: list[EvidenceInput] = []
        for item in items:
            source_id = str(item.get("source_id", ""))
            if source_id not in allowed_source_ids:
                continue
            result.append(
                EvidenceInput(
                    source_id=source_id,
                    quote=item.get("quote", ""),
                    page_number=item.get("page_number"),
                    start_offset=item.get("start_offset"),
                    end_offset=item.get("end_offset"),
                )
            )
        return tuple(result)

    @staticmethod
    def _parse_optional_date(value: Any) -> date | None:
        if value is None or value == "":
            return None
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        try:
            return datetime.strptime(str(value), "%Y-%m-%d").date()
        except ValueError:
            return None
