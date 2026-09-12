from __future__ import annotations

import io
from dataclasses import dataclass
from typing import TYPE_CHECKING
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as _canvas_module
from reportlab.platypus import Flowable
from reportlab.platypus import Paragraph
from reportlab.platypus import SimpleDocTemplate
from reportlab.platypus import Table
from reportlab.platypus import TableStyle

if TYPE_CHECKING:
    from collections.abc import Callable
    from collections.abc import Sequence

    from reportlab.pdfgen.canvas import Canvas
    from reportlab.platypus.doctemplate import BaseDocTemplate

ACCENT = colors.HexColor("#1F3A5F")
GRID = colors.HexColor("#9AA5B1")
ZEBRA = colors.HexColor("#F2F5F8")
MUTED = colors.HexColor("#555555")


@dataclass(frozen=True, slots=True)
class ReportStyles:
    """Named paragraph styles shared by every generated PDF report."""

    title: ParagraphStyle
    body: ParagraphStyle
    cell: ParagraphStyle
    cell_id: ParagraphStyle
    heading: ParagraphStyle
    note: ParagraphStyle
    footnote: ParagraphStyle


def build_styles() -> ReportStyles:
    """Create the shared report style sheet (single source of report typography)."""
    styles = getSampleStyleSheet()
    body = ParagraphStyle(
        "ReportBody",
        parent=styles["Normal"],
        fontSize=9.5,
        leading=13,
        alignment=TA_LEFT,
    )
    return ReportStyles(
        title=styles["Title"],
        body=body,
        cell=ParagraphStyle("ReportCell", parent=body, fontSize=8.5, leading=11),
        cell_id=ParagraphStyle("ReportCellId", parent=body, fontSize=7, leading=8.5),
        heading=ParagraphStyle(
            "ReportHeading",
            parent=styles["Heading2"],
            fontSize=13,
            leading=16,
            spaceBefore=8,
            spaceAfter=4,
            textColor=ACCENT,
        ),
        note=ParagraphStyle(
            "ReportNote",
            parent=body,
            fontName="Helvetica-Oblique",
            textColor=MUTED,
        ),
        footnote=ParagraphStyle(
            "ReportFootnote",
            parent=body,
            fontSize=8,
            leading=10.5,
            leftIndent=10 * mm,
            firstLineIndent=-10 * mm,
        ),
    )


def render_table(
    *,
    headers: Sequence[str],
    widths: Sequence[float],
    rows: Sequence[Sequence[object]],
    cell_style: ParagraphStyle,
    empty_note: str,
    note_style: ParagraphStyle,
) -> Flowable:
    """Render a zebra-striped, grid-bordered table of Paragraph cells.

    Cell values may be plain strings (escaped and wrapped in ``cell_style``
    paragraphs) or pre-built flowables (inserted verbatim).
    """
    if not rows:
        return Paragraph(empty_note, note_style)
    data: list[Sequence[object]] = [list(headers)]
    data.extend(
        [value if isinstance(value, Flowable) else Paragraph(escape(str(value)), cell_style)
         for value in row]
        for row in rows
    )
    table = Table(data, colWidths=list(widths), repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 8.5),
                ("GRID", (0, 0), (-1, -1), 0.4, GRID),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ZEBRA]),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return table


def format_confidence(confidence: float | None) -> str:
    return "-" if confidence is None else f"{confidence:.0%}"


def build_pdf(
    story: Sequence[Flowable],
    *,
    doc_title: str,
    footer_text: str,
    pagesize: tuple[float, float] = A4,
    uncompressed_text: bool = False,
) -> bytes:
    """Lay out *story* on an A4 (or custom-sized) document with a page footer.

    ``uncompressed_text=True`` disables page-content compression so the
    rendered body text remains searchable in the raw PDF bytes (useful for
    downstream tools and tests that look for change identifiers).
    """
    buffer = io.BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=pagesize,
        title=doc_title,
        author="Post-Meeting Legal Analyzer",
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=24 * mm,
    )
    canvasmaker: type[Canvas]
    if uncompressed_text:

        class _UncompressedCanvas(_canvas_module.Canvas):
            def __init__(self, *args: object, **kwargs: object) -> None:
                kwargs["pageCompression"] = 0
                super().__init__(*args, **kwargs)  # type: ignore[arg-type]

        canvasmaker = _UncompressedCanvas
    else:
        canvasmaker = _canvas_module.Canvas
    on_page: Callable[[Canvas, BaseDocTemplate], None] = page_footer(footer_text)
    document.build(story, onFirstPage=on_page, onLaterPages=on_page, canvasmaker=canvasmaker)
    return buffer.getvalue()


def page_footer(footer_text: str) -> Callable[[Canvas, BaseDocTemplate], None]:
    """Return an on-page callback drawing *footer_text* centred at the bottom."""

    def _draw_page_footer(canvas: Canvas, document: BaseDocTemplate) -> None:
        page_width, _page_height = document.pagesize
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawCentredString(page_width / 2, 12 * mm, footer_text)
        canvas.restoreState()

    return _draw_page_footer
