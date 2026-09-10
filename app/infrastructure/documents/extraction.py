from __future__ import annotations

import io
from pathlib import Path

from app.core.exceptions.domain import FileProcessingError
from app.core.exceptions.domain import ValidationError

_PDF_MAGIC = b"%PDF"
_ZIP_MAGIC = b"PK\x03\x04"

SUPPORTED_EXTENSIONS: tuple[str, ...] = (".pdf", ".docx", ".txt", ".md")

SUPPORTED_FORMATS_HINT = "PDF (.pdf), DOCX (.docx), TXT (.txt), Markdown (.md)"

_EMPTY_TEXT_DETAIL = "No extractable text — scanned/image-only files are not supported yet"


def extract_text(filename: str, data: bytes) -> str:
    """Extract plain text from uploaded document bytes.

    Format is chosen by file extension and validated by content sniffing
    (PDF/DOCX magic bytes).  Raises a domain ``ValidationError`` (HTTP 422)
    for unsupported or mismatched formats and ``FileProcessingError``
    (HTTP 422) when the document carries no extractable text.
    """
    extension = Path(filename).suffix.lower()

    if extension == ".pdf":
        text = _extract_pdf(data, filename)
    elif extension == ".docx":
        text = _extract_docx(data, filename)
    elif extension in (".txt", ".md"):
        text = data.decode("utf-8", errors="replace")
    else:
        raise ValidationError(
            detail=(
                f"Unsupported file format '{extension or 'unknown'}'. "
                f"Supported formats: {SUPPORTED_FORMATS_HINT}"
            ),
            field="file",
        )

    if not text.strip():
        raise FileProcessingError(detail=_EMPTY_TEXT_DETAIL, filename=filename)
    return text


def _extract_pdf(data: bytes, filename: str) -> str:
    if not data.startswith(_PDF_MAGIC):
        raise ValidationError(
            detail=f"File '{filename}' has a .pdf extension but its content is not a PDF",
            field="file",
        )
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        pages = [page.extract_text() or "" for page in reader.pages]
    except Exception as exc:
        raise FileProcessingError(
            detail=f"Failed to read PDF: {exc}",
            filename=filename,
        ) from exc
    return "\n\n".join(pages)


def _extract_docx(data: bytes, filename: str) -> str:
    if not data.startswith(_ZIP_MAGIC):
        raise ValidationError(
            detail=f"File '{filename}' has a .docx extension but its content is not a DOCX",
            field="file",
        )
    try:
        from docx import Document

        document = Document(io.BytesIO(data))
        paragraphs = [paragraph.text for paragraph in document.paragraphs]
    except Exception as exc:
        raise FileProcessingError(
            detail=f"Failed to read DOCX: {exc}",
            filename=filename,
        ) from exc
    return "\n\n".join(paragraphs)
