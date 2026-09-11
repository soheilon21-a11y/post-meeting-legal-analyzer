from __future__ import annotations

import io
from datetime import UTC
from datetime import datetime
from typing import TYPE_CHECKING
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph
from reportlab.platypus import SimpleDocTemplate
from reportlab.platypus import Spacer
from reportlab.platypus import Table
from reportlab.platypus import TableStyle

if TYPE_CHECKING:
    from collections.abc import Sequence

    from reportlab.pdfgen.canvas import Canvas
    from reportlab.platypus.doctemplate import BaseDocTemplate
    from reportlab.platypus.flowables import Flowable

    from app.db.models.analysis import Analysis
    from app.db.models.analysis import AnalysisItem
    from app.db.models.analysis import Citation

REPORT_TITLE = "Legal Analysis Report"
REPORT_FOOTER = (
    "Generated locally by Post-Meeting Legal Analyzer"
    " \u2014 ready_for_review by responsible attorney"
)

_ACCENT = colors.HexColor("#1F3A5F")
_GRID = colors.HexColor("#9AA5B1")
_ZEBRA = colors.HexColor("#F2F5F8")
_MUTED = colors.HexColor("#555555")

_RISK_TYPES = frozenset({"risk"})
_OBLIGATION_TYPES = frozenset({"obligation", "deadline"})
_TRANSCRIPT_SOURCE_TYPES = frozenset({"transcript", "meeting", "meeting_transcript"})


def render_analysis_report_pdf(analysis: Analysis) -> bytes:
    """Render an ORM ``Analysis`` (with items and citations) as PDF bytes."""
    buffer = io.BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        title=REPORT_TITLE,
        author="Post-Meeting Legal Analyzer",
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=24 * mm,
    )
    styles = getSampleStyleSheet()
    body = ParagraphStyle(
        "ReportBody",
        parent=styles["Normal"],
        fontSize=9.5,
        leading=13,
        alignment=TA_LEFT,
    )
    cell = ParagraphStyle("ReportCell", parent=body, fontSize=8.5, leading=11)
    heading = ParagraphStyle(
        "ReportHeading",
        parent=styles["Heading2"],
        fontSize=13,
        leading=16,
        spaceBefore=8,
        spaceAfter=4,
        textColor=_ACCENT,
    )
    note = ParagraphStyle(
        "ReportNote",
        parent=body,
        fontName="Helvetica-Oblique",
        textColor=_MUTED,
    )
    footnote = ParagraphStyle(
        "ReportFootnote",
        parent=body,
        fontSize=8,
        leading=10.5,
        leftIndent=10 * mm,
        firstLineIndent=-10 * mm,
    )

    footnotes = _Footnotes()
    risks, obligations, actions = _split_items(analysis.items or ())

    story: list[Flowable] = []
    story.append(Paragraph(REPORT_TITLE, styles["Title"]))
    generated_at = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    story.append(
        Paragraph(
            f"Analysis ID: {escape(str(analysis.id))}<br/>"
            f"Status: {escape(str(analysis.status))}<br/>"
            f"Generated: {generated_at}",
            body,
        )
    )
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph("Summary", heading))
    summary = (analysis.result_metadata or {}).get("summary")
    if summary:
        story.append(Paragraph(escape(str(summary)), body))
    else:
        story.append(Paragraph("No summary recorded.", note))

    story.append(Paragraph("Risks", heading))
    story.append(
        _render_table(
            headers=("#", "Title", "Description", "Risk level", "Confidence", "Sources"),
            widths=(8 * mm, 40 * mm, 74 * mm, 18 * mm, 18 * mm, 14 * mm),
            rows=[
                (
                    str(index),
                    item.title or "",
                    item.description or "",
                    item.severity or "-",
                    _format_confidence(item.confidence_score),
                    footnotes.markers(item.citations or ()),
                )
                for index, item in enumerate(risks, start=1)
            ],
            cell_style=cell,
            empty_note="No risks identified.",
            note_style=note,
        )
    )

    story.append(Paragraph("Obligations", heading))
    story.append(
        _render_table(
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
            cell_style=cell,
            empty_note="No obligations identified.",
            note_style=note,
        )
    )

    story.append(Paragraph("Action items", heading))
    story.append(
        _render_table(
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
            cell_style=cell,
            empty_note="No action items identified.",
            note_style=note,
        )
    )

    if footnotes.entries:
        story.append(Paragraph("Sources & citations", heading))
        for line in footnotes.entries:
            story.append(Paragraph(line, footnote))

    document.build(story, onFirstPage=_draw_page_footer, onLaterPages=_draw_page_footer)
    return buffer.getvalue()


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


def _render_table(
    *,
    headers: Sequence[str],
    widths: Sequence[float],
    rows: Sequence[Sequence[str]],
    cell_style: ParagraphStyle,
    empty_note: str,
    note_style: ParagraphStyle,
) -> Flowable:
    if not rows:
        return Paragraph(empty_note, note_style)
    data: list[Sequence[object]] = [list(headers)]
    data.extend([Paragraph(escape(value), cell_style) for value in row] for row in rows)
    table = Table(data, colWidths=list(widths), repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), _ACCENT),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 8.5),
                ("GRID", (0, 0), (-1, -1), 0.4, _GRID),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _ZEBRA]),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return table


def _format_confidence(confidence: float | None) -> str:
    return "-" if confidence is None else f"{confidence:.0%}"


def _format_due_date(due_date: object) -> str:
    if due_date is None:
        return "-"
    if isinstance(due_date, datetime):
        return due_date.strftime("%Y-%m-%d")
    return str(due_date)


def _draw_page_footer(canvas: Canvas, document: BaseDocTemplate) -> None:
    page_width, _page_height = document.pagesize
    canvas.saveState()
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(_MUTED)
    canvas.drawCentredString(page_width / 2, 12 * mm, REPORT_FOOTER)
    canvas.restoreState()
