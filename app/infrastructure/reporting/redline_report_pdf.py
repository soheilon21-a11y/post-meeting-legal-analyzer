from __future__ import annotations

from datetime import UTC
from datetime import datetime
from typing import TYPE_CHECKING
from xml.sax.saxutils import escape

from reportlab.lib.pagesizes import A4
from reportlab.lib.pagesizes import landscape
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

    from app.db.models.redline import RedlineJob

REPORT_TITLE = "Redline Review Report"
REPORT_FOOTER = (
    "Generated locally by Post-Meeting Legal Analyzer"
    " — subject to review by the responsible attorney"
)


def render_redline_report_pdf(job: RedlineJob) -> bytes:
    """Render an ORM ``RedlineJob`` (with changes and citations) as PDF bytes.

    The report carries a header (id, status, generation date), the base and
    comparison document identifiers, a landscape table of proposed changes
    (clause path, original/proposed text, rationale, risk, confidence, review
    status) and verbatim citation footnotes.  Body text is emitted
    uncompressed so change ids stay searchable in the raw PDF bytes.
    """
    styles = build_styles()
    footnotes = _RedlineFootnotes()

    story: list[Flowable] = []
    story.append(Paragraph(REPORT_TITLE, styles.title))
    generated_at = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    story.append(
        Paragraph(
            f"Redline ID: {escape(str(job.id))}<br/>"
            f"Status: {escape(str(job.status))}<br/>"
            f"Generated: {generated_at}",
            styles.body,
        )
    )
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph("Documents under review", styles.heading))
    story.append(
        render_table(
            headers=("Role", "Document version id", "Source document"),
            widths=(28 * mm, 64 * mm, 120 * mm),
            rows=[
                (
                    "Base",
                    str(job.base_document_version_id),
                    _document_label(job.base_version),
                ),
                (
                    "Comparison",
                    str(job.comparison_document_version_id),
                    _document_label(job.comparison_version),
                ),
            ],
            cell_style=styles.cell,
            empty_note="No documents linked.",
            note_style=styles.note,
        )
    )

    story.append(Paragraph(f"Proposed changes ({len(job.changes or ())})", styles.heading))
    story.append(
        render_table(
            headers=(
                "Change id",
                "Clause",
                "Original text",
                "Proposed text",
                "Rationale",
                "Risk",
                "Confidence",
                "Review",
                "Sources",
            ),
            widths=(
                56 * mm,
                22 * mm,
                40 * mm,
                40 * mm,
                30 * mm,
                12 * mm,
                14 * mm,
                15 * mm,
                12 * mm,
            ),
            rows=[
                (
                    Paragraph(str(change.id), styles.cell_id),
                    change.section_path or "-",
                    change.original_text or "",
                    change.proposed_text or "",
                    change.rationale or "",
                    change.risk_level or "-",
                    format_confidence(change.confidence),
                    str(change.review_status),
                    footnotes.markers(change.source_citations),
                )
                for change in (job.changes or ())
            ],
            cell_style=styles.cell,
            empty_note="No changes have been generated for this redline job.",
            note_style=styles.note,
        )
    )

    if footnotes.entries:
        story.append(Paragraph("Sources & citations", styles.heading))
        for line in footnotes.entries:
            story.append(Paragraph(line, styles.footnote))

    return build_pdf(
        story,
        doc_title=REPORT_TITLE,
        footer_text=REPORT_FOOTER,
        pagesize=landscape(A4),
        uncompressed_text=True,
    )


class _RedlineFootnotes:
    """Collects citation footnotes from ``RedlineChange.source_citations`` dicts."""

    def __init__(self) -> None:
        self.entries: list[str] = []

    def markers(self, citations: Sequence[object] | None) -> str:
        return " ".join(
            self._register(citation)
            for citation in citations or ()
            if isinstance(citation, dict) and str(citation.get("quote") or "").strip()
        )

    def _register(self, citation: dict) -> str:
        index = len(self.entries) + 1
        location = escape(str(citation.get("source_id") or "supplied context"))
        page_number = citation.get("page_number")
        if page_number is not None:
            location = f"{location}, page {page_number}"
        quote = escape(str(citation.get("quote") or ""))
        self.entries.append(f'[{index}] "{quote}" &mdash; source: {location}')
        return f"[{index}]"


def _document_label(version: object) -> str:
    if version is None:
        return "document not linked"
    document = getattr(version, "document", None)
    if document is None:
        return "uploaded document"
    title = str(getattr(document, "title", "") or "").strip() or "untitled"
    filename = str(getattr(document, "source_filename", "") or "").strip()
    return f"{title} ({filename})" if filename else title
