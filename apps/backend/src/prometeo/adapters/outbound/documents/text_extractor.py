"""Plain-text extraction from PSI documents: PDF (pypdf), DOCX and PPTX (zip + XML).

Text only. Scanned PDFs yield no text and are reported as such upstream; there is no OCR.
Legacy binary `.doc` / `.ppt` files are not supported. PDF support needs the `knowledge` extra
(`uv sync --extra knowledge`).
"""

from __future__ import annotations

import io
import logging
import re
import zipfile
from xml.etree import ElementTree

from prometeo.application.ports.outbound import ExtractedPage

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
_SLIDE = re.compile(r"ppt/slides/slide(\d+)\.xml$")
_SUPPORTED = frozenset({"pdf", "docx", "pptx"})


class DocumentTextExtractor:
    def supports(self, file_name: str) -> bool:
        return _extension(file_name) in _SUPPORTED

    def extract(self, file_name: str, content: bytes) -> list[ExtractedPage]:
        extension = _extension(file_name)
        if extension == "pdf":
            return _pdf(content)
        if extension == "docx":
            return _docx(content)
        if extension == "pptx":
            return _pptx(content)
        raise ValueError(f"unsupported document type: {file_name}")


def _extension(file_name: str) -> str:
    _, dot, ext = file_name.rpartition(".")
    return ext.lower() if dot else ""


def _pdf(content: bytes) -> list[ExtractedPage]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - depends on the optional extra
        raise RuntimeError("PDF extraction needs `uv sync --extra knowledge`") from exc

    # pypdf logs a warning per unusual font; they say nothing about whether text was read.
    logging.getLogger("pypdf").setLevel(logging.ERROR)
    reader = PdfReader(io.BytesIO(content))
    pages: list[ExtractedPage] = []
    for number, page in enumerate(reader.pages, start=1):
        text: str = page.extract_text() or ""
        if text.strip():
            pages.append(ExtractedPage(text=text, page=str(number)))
    return pages


def _docx(content: bytes) -> list[ExtractedPage]:
    """A .docx has no fixed pages, so the whole body is one unit with no page label."""
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        root = ElementTree.fromstring(archive.read("word/document.xml"))
    paragraphs = []
    for paragraph in root.iter(f"{_W}p"):
        text = "".join(node.text or "" for node in paragraph.iter(f"{_W}t")).strip()
        if text:
            paragraphs.append(text)
    body = "\n\n".join(paragraphs)
    return [ExtractedPage(text=body, page=None)] if body else []


def _pptx(content: bytes) -> list[ExtractedPage]:
    pages: list[ExtractedPage] = []
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        slides = sorted(
            (int(match.group(1)), name)
            for name in archive.namelist()
            if (match := _SLIDE.search(name))
        )
        for number, name in slides:
            root = ElementTree.fromstring(archive.read(name))
            lines = []
            for paragraph in root.iter(f"{_A}p"):
                text = "".join(node.text or "" for node in paragraph.iter(f"{_A}t")).strip()
                if text:
                    lines.append(text)
            if lines:
                pages.append(ExtractedPage(text="\n\n".join(lines), page=f"slide {number}"))
    return pages
