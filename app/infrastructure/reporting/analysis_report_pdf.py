from __future__ import annotations

from datetime import UTC
from datetime import datetime
from typing import TYPE_CHECKING
from xml.sax.saxutils import escape

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph
from reportlab.platypus import Spacer

from app.infrastructure.reporting.pdf_report_style import build_pdf
from app.infrastructure.reporting.pdf_report_style import build_styles
from app.infrastructure.reporting.pdf_report_style import format_confidence
from app.infrastructure.reporting.pdf_report_style import render_table

if TYPE_CHECKING:
    from collections.abc import Sequence

    from reportlab.platypus.flowables import Flowable

    from app.db.models.analysis import Analysis
    from app.db.models.analysis import AnalysisItem
    from app.db.models.analysis import Citation

REPORT_TITLE = "Legal Analysis Report"
REPORT_FOOTER = (
    "Generated locally by Post-Meeting Legal Analyzer"
    " â€” ready_for_review by responsible attorney"
)

_RISK_TYPES = frozenset({"risk"})
_OBLIGATION_TYPES = frozenset({"obligation", "deadline"})
_TRANSCRIPT_SOURCE_TYPES = frozenset({"transcript", "meeting", "meeting_transcript"})


def render_analysis_report_pdf(analysis: Analysis) -> bytes:
    """Render an ORM ``Analysis`` (with items and citations) as PDF bytes."""
    styles = build_styles()

    footnotes = _Footnotes()
    risks, obligations, actions = _split_items(analysis.items or ())

    story: list[Flowable] = []
    story.append(Paragraph(REPORT_TITLE, styles.title))
    generated_at = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    story.append(
        Paragraph(
            f"Analysis ID: {escape(str(analysis.id))}<br/>"
            f"Status: {escape(str(analysis.status))}<br/>"
            f"Generated: {generated_at}",
            styles.body,
        )
    )
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph("Summary", styles.heading))
    summary = (analysis.result_metadata or {}).get("summary")
    if summary:
        story.append(Paragraph(escape(str(summary)), styles.body))
    else:
        story.append(Paragraph("No summary recorded.", styles.note))

    story.append(Paragraph("Risks", styles.heading))
    story.append(
        render_table(
            headers=("#", "Title", "Description", "Risk level", "Confidence", "Sources"),
            widths=(8 * mm, 40 * mm, 74 * mm, 18 * mm, 18 * mm, 14 * mm),
            rows=[
                (
                    str(index),
                    item.title or "",
                    item.description or "",
                    item.severity or "-",
                    format_confidence(item.confidence_score),
                    footnotes.markers(item.citations or ()),
                )
                for index, item in enumerate(risks, start=1)
            ],
            cell_style=styles.cell,
            empty_note="No risks identified.",
            note_style=styles.note,
        )
    )

    story.append(Paragraph("Obligations", styles.heading))
    story.append(
        render_table(
            headers=("#", "Description", "Responsible party", "Due date", "Sources"),
            widths=(8 * mm, 96 * mm, 30 * mm, 22 * mm, 16 * mm),
            rows=[
                (
                    str(index),
                    item.description or item.title or "",
                    item.responsible_party or "-",
                    _format_due_date(item.due_date),
                    footnotes.markers(item.citations or ()),
                )
                for index, item in enumerate(obligations, start=1)
            ],
            cell_style=styles.cell,
            empty_note="No obligations identified.",
            note_style=styles.note,
        )
    )

    story.append(Paragraph("Action items", styles.heading))
    story.append(
        render_table(
            headers=("#", "Title", "Description", "Responsible party", "Due date", "Sources"),
            widths=(8 * mm, 34 * mm, 64 * mm, 30 * mm, 20 * mm, 16 * mm),
            rows=[
                (
                    str(index),
                    item.title or "",
                    item.description or "",
                    item.responsible_party or "-",
                    _format_due_date(item.due_date),
                    footnotes.markers(item.citations or ()),
                )
                for index, item in enumerate(actions, start=1)
            ],
            cell_style=styles.cell,
            empty_note="No action items identified.",
            note_style=styles.note,
        )
    )

    if footnotes.entries:
        story.append(Paragraph("Sources & citations", styles.heading))
        for line in footnotes.entries:
            story.append(Paragraph(line, styles.footnote))

    return build_pdf(story, doc_title=REPORT_TITLE, footer_text=REPORT_FOOTER, pagesize=A4)


class _Footnotes:
    """Collects citation footnotes and hands out [n] markers for table cells."""

    def __init__(self) -> None:
        self.entries: list[str] = []

    def markers(self, citations: Sequence[Citation]) -> str:
        return " ".join(self._register(citation) for citation in citations if citation.quoted_text)

    def _register(self, citation: Citation) -> str:
        index = len(self.entries) + 1
        location = _source_label(citation)
        if citation.page_number is not None:
            location = f"{location}, page {citation.page_number}"
        quote = escape(citation.quoted_text or "")
        self.entries.append(f'[{index}] "{quote}" &mdash; {location}')
        return f"[{index}]"


def _source_label(citation: Citation) -> str:
    source_type = str(citation.source_type or "").strip().lower()
    if source_type in _TRANSCRIPT_SOURCE_TYPES:
        return "meeting transcript"
    return f"corpus source: {escape(str(citation.source_id))}"


def _split_items(
    items: Sequence[AnalysisItem],
) -> tuple[list[AnalysisItem], list[AnalysisItem], list[AnalysisItem]]:
    risks: list[AnalysisItem] = []
    obligations: list[AnalysisItem] = []
    actions: list[AnalysisItem] = []
    for item in items:
        item_type = str(item.item_type)
        if item_type in _RISK_TYPES:
            risks.append(item)
        elif item_type in _OBLIGATION_TYPES:
            obligations.append(item)
        else:
            actions.append(item)
    return risks, obligations, actions


def _format_due_date(due_date: object) -> str:
    if due_date is None:
        return "-"
    if isinstance(due_date, datetime):
        return due_date.strftime("%Y-%m-%d")
    return str(due_date)
