from __future__ import annotations

import io
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest
from docx import Document
from httpx import ASGITransport
from httpx import AsyncClient
from reportlab.pdfgen import canvas

from app.api.v1 import corpus as corpus_api
from app.main import create_app

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.application.dtos.internal.vector_index import IndexedChunk


TRANSCRIPT = (
    "MEMO OF MEETING: The parties discussed the indemnification cap in the "
    "merger agreement.\n\n"
    "Counsel for the buyer proposed a cap at twenty percent of the purchase "
    "price."
)

PDF_LINES = [
    "The parties discussed the indemnification cap.",
    "Counsel proposed twenty percent of the price.",
]


class FakeEmbeddings:
    async def embed(self, texts: Sequence[str]) -> tuple[tuple[float, ...], ...]:
        return tuple((0.1 * (position + 1),) for position in range(len(texts)))


class FakeIndex:
    def __init__(self) -> None:
        self.upserted: list[IndexedChunk] = []

    async def upsert(self, items: Sequence[IndexedChunk]) -> None:
        self.upserted.extend(items)


@pytest.fixture
def fake_pipeline(monkeypatch: pytest.MonkeyPatch) -> tuple[FakeEmbeddings, FakeIndex]:
    embeddings = FakeEmbeddings()
    index = FakeIndex()
    monkeypatch.setattr(corpus_api, "OllamaEmbeddings", lambda: embeddings)
    monkeypatch.setattr(
        corpus_api,
        "QdrantVectorIndex",
        SimpleNamespace(from_settings=lambda: index),
    )
    return embeddings, index


def _client() -> AsyncClient:
    app = create_app()
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _docx_bytes(paragraphs: Sequence[str]) -> bytes:
    document = Document()
    for paragraph in paragraphs:
        document.add_paragraph(paragraph)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def _pdf_bytes(lines: Sequence[str]) -> bytes:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.setFont("Helvetica", 12)
    y_position = 720
    for line in lines:
        pdf.drawString(72, y_position, line)
        y_position -= 16
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


@pytest.mark.anyio
async def test_upload_txt_returns_success_and_indexes_chunks(
    fake_pipeline: tuple[FakeEmbeddings, FakeIndex],
) -> None:
    _, index = fake_pipeline

    async with _client() as client:
        response = await client.post(
            "/api/v1/corpus/documents/upload",
            files={"file": ("transcript.txt", TRANSCRIPT.encode("utf-8"), "text/plain")},
            data={"matter_id": "matter-1"},
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["source_id"] == "transcript"
    assert body["matter_id"] == "matter-1"
    assert body["chunks_indexed"] > 0
    assert len(index.upserted) == body["chunks_indexed"]
    assert all(item.matter_id == "matter-1" for item in index.upserted)


@pytest.mark.anyio
async def test_upload_docx_returns_success_and_indexes_chunks(
    fake_pipeline: tuple[FakeEmbeddings, FakeIndex],
) -> None:
    _, index = fake_pipeline
    data = _docx_bytes(TRANSCRIPT.split("\n\n"))

    async with _client() as client:
        response = await client.post(
            "/api/v1/corpus/documents/upload",
            files={
                "file": (
                    "contract.docx",
                    data,
                    "application/vnd.openxmlformats-officedocument" ".wordprocessingml.document",
                )
            },
            data={"matter_id": "matter-2", "source_id": "custom-source"},
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["source_id"] == "custom-source"
    assert body["chunks_indexed"] > 0
    assert all(
        "indemnification" in item.text or "twenty percent" in item.text for item in index.upserted
    )


@pytest.mark.anyio
async def test_upload_pdf_returns_success_and_indexes_chunks(
    fake_pipeline: tuple[FakeEmbeddings, FakeIndex],
) -> None:
    _, index = fake_pipeline
    data = _pdf_bytes(PDF_LINES)

    async with _client() as client:
        response = await client.post(
            "/api/v1/corpus/documents/upload",
            files={"file": ("minutes.pdf", data, "application/pdf")},
            data={"matter_id": "matter-3"},
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["source_id"] == "minutes"
    assert body["chunks_indexed"] > 0
    assert index.upserted


@pytest.mark.anyio
async def test_upload_unsupported_extension_returns_422(
    fake_pipeline: tuple[FakeEmbeddings, FakeIndex],
) -> None:
    _, index = fake_pipeline

    async with _client() as client:
        response = await client.post(
            "/api/v1/corpus/documents/upload",
            files={
                "file": (
                    "budget.xlsx",
                    b"PK\x03\x04fake-spreadsheet",
                    "application/vnd.ms-excel",
                )
            },
            data={"matter_id": "matter-4"},
        )

    assert response.status_code == 422, response.text
    assert (
        "Supported formats: PDF (.pdf), DOCX (.docx), TXT (.txt), Markdown (.md)"
        in response.json()["detail"]
    )
    assert index.upserted == []


@pytest.mark.anyio
async def test_upload_pdf_without_extractable_text_returns_422(
    fake_pipeline: tuple[FakeEmbeddings, FakeIndex],
) -> None:
    _, index = fake_pipeline
    data = _pdf_bytes([])

    async with _client() as client:
        response = await client.post(
            "/api/v1/corpus/documents/upload",
            files={"file": ("scan.pdf", data, "application/pdf")},
            data={"matter_id": "matter-5"},
        )

    assert response.status_code == 422, response.text
    assert "No extractable text" in response.json()["detail"]
    assert index.upserted == []


@pytest.mark.anyio
async def test_upload_oversized_file_returns_413(
    fake_pipeline: tuple[FakeEmbeddings, FakeIndex],
) -> None:
    _, index = fake_pipeline
    payload = b"x" * (corpus_api.MAX_UPLOAD_BYTES + 1)

    async with _client() as client:
        response = await client.post(
            "/api/v1/corpus/documents/upload",
            files={"file": ("huge.txt", payload, "text/plain")},
            data={"matter_id": "matter-6"},
        )

    assert response.status_code == 413, response.text
    assert "exceeds maximum" in response.json()["detail"]
    assert index.upserted == []
