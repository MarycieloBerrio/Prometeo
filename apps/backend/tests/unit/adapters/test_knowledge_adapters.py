"""Pure parts of the knowledge-base adapters: no network, no database, no model download.
Payloads below copy the SHAPE of the PSI API; their values are INVENTED test data."""

from __future__ import annotations

import io
import zipfile
from datetime import date

import pytest

from prometeo.adapters.outbound.documents.text_extractor import DocumentTextExtractor
from prometeo.adapters.outbound.nasa.psi_client import parse_investigation
from prometeo.adapters.outbound.persistence.postgres_knowledge_store import vector_literal
from prometeo.adapters.outbound.retrieval.pgvector_retriever import or_tsquery
from prometeo.application.ports.outbound import KnowledgeSourceError

PAYLOAD = {
    "accession": "TEST-7",
    "title": " Invented Investigation ",
    "investigationAcronym": "",
    "doi": "10.0000/abcd",
    "version": 4,
    "licenseIdentifier": "CC0-1.0",
    "researchArea": "Combustion Science",
    "subResearchArea": "",
    "projectType": "Microgravity Investigation",
    "flightProgram": "International Space Station (ISS)",
    "experimentHardware": "Glovebox",
    "investigationStartDate": "01-31-2010",
    "investigationEndDate": "not a date",
    "objective": "Objective text.",
    "approach": "",
    "hypothesis": "Hypothesis text.",
    "researchImpacts": "Impact text.",
    "related_glds": "TEST-8, TEST-9",
    "managingNasaCenter": "Invented Center",
    "totalFileSize": 12.0,
    "public": True,
    "added": [
        {
            "file_name": "TEST-7_Reports_Final.pdf",
            "file_size": 2048.0,
            "remote_path": "/Home/psi-data/TEST-7/Reports/TEST-7_Reports_Final.pdf",
            "remote_url": "https://example.test/file/1",
            "resource_id": {"$oid": "abc123"},
            "restricted": False,
            "subcategory": "",
            "version": 2,
            "visible": True,
        },
        {
            "file_name": "hidden.zip",
            "file_size": 1,
            "remote_path": "/Home/psi-data/TEST-7/Raw Data/Run 1/hidden.zip",
            "visible": False,
        },
        {
            "file_name": "run.mp4",
            "file_size": 5,
            "remote_path": "/Home/psi-data/TEST-7/Raw Data/Run 1/run.mp4",
            "subcategory": "Run 1",
            "restricted": True,
        },
    ],
    "experimentalTable": [
        {
            "file_name": "TEST-7_Experimental table_T.csv",
            "file_size": 100,
            "remote_path": "/Home/psi-data/TEST-7/Experimental table/T.csv",
        }
    ],
    "publications": [
        {
            "authorList": "A. Author",
            "doi": "",
            "title": "An invented paper",
            "status": {"annotationValue": "published"},
        },
        {"authorList": "Nobody", "doi": "", "title": ""},
    ],
}


def test_parse_investigation_maps_psi_fields_without_inventing_values() -> None:
    inv = parse_investigation(PAYLOAD, "https://example.test")
    assert inv.accession == "TEST-7"
    assert inv.title == "Invented Investigation"
    assert inv.acronym is None  # empty string stays unknown
    assert inv.code == "TEST-7"  # falls back to the accession
    assert inv.url == "https://example.test/physci/repo/data/investigations/TEST-7"
    assert inv.sub_research_area is None
    assert inv.start_date == date(2010, 1, 31)
    assert inv.end_date is None  # unparseable date stays unknown
    assert inv.approach is None
    assert inv.related_accessions == ("TEST-8", "TEST-9")
    assert [name for name, _ in inv.narrative_sections()] == [
        "Objectives",
        "Hypothesis",
        "Research impacts",
    ]
    assert inv.extra == {"managingNasaCenter": "Invented Center", "totalFileSize": "12.0"}


def test_parse_investigation_reads_files_tables_and_publications() -> None:
    inv = parse_investigation(PAYLOAD)
    report, video = inv.files  # the invisible file is dropped
    assert report.category == "Reports"
    assert report.size_bytes == 2048
    assert report.resource_id == "abc123"
    assert report.subcategory is None
    assert report.extension == "pdf"
    assert video.category == "Raw Data"
    assert video.subcategory == "Run 1"
    assert video.restricted is True
    assert video.resource_id is None
    assert inv.tables[0].category == "Experimental table"
    assert [(p.title, p.doi, p.status) for p in inv.publications] == [
        ("An invented paper", None, "published")
    ]


def test_parse_investigation_rejects_a_payload_without_accession() -> None:
    with pytest.raises(KnowledgeSourceError):
        parse_investigation({"title": "x"})


def _zip(files: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, body in files.items():
            archive.writestr(name, body)
    return buffer.getvalue()


def test_docx_text_is_extracted_paragraph_by_paragraph() -> None:
    w = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    xml = (
        f'<w:document xmlns:w="{w}"><w:body>'
        "<w:p><w:r><w:t>First </w:t></w:r><w:r><w:t>paragraph.</w:t></w:r></w:p>"
        "<w:p></w:p>"
        "<w:p><w:r><w:t>Second paragraph.</w:t></w:r></w:p>"
        "</w:body></w:document>"
    )
    pages = DocumentTextExtractor().extract("a.docx", _zip({"word/document.xml": xml}))
    assert [(p.page, p.text) for p in pages] == [(None, "First paragraph.\n\nSecond paragraph.")]


def test_pptx_text_is_extracted_per_slide_in_order() -> None:
    a = "http://schemas.openxmlformats.org/drawingml/2006/main"

    def slide(text: str) -> str:
        return f'<p:sld xmlns:p="x" xmlns:a="{a}"><a:p><a:r><a:t>{text}</a:t></a:r></a:p></p:sld>'

    content = _zip(
        {
            "ppt/slides/slide10.xml": slide("Ten"),
            "ppt/slides/slide2.xml": slide("Two"),
            "ppt/slides/slide3.xml": '<p:sld xmlns:p="x"/>',
        }
    )
    pages = DocumentTextExtractor().extract("a.pptx", content)
    assert [(p.page, p.text) for p in pages] == [("slide 2", "Two"), ("slide 10", "Ten")]


def test_extractor_supports_only_formats_it_can_read() -> None:
    extractor = DocumentTextExtractor()
    assert extractor.supports("Report.PDF")
    assert extractor.supports("a.docx") and extractor.supports("a.pptx")
    assert not extractor.supports("old.doc")
    assert not extractor.supports("video.mp4")
    with pytest.raises(ValueError):
        extractor.extract("old.doc", b"")


def test_or_tsquery_keeps_alphanumeric_terms_once() -> None:
    assert or_tsquery("How does PMMA burn? PMMA!") == "how | does | pmma | burn"
    assert or_tsquery("O2 & (flow) | 'x'") == "o2 | flow"
    assert or_tsquery("?!") == ""


def test_vector_literal_is_pgvector_text_format() -> None:
    assert vector_literal([0.5, -1, 2]) == "[0.5,-1.0,2.0]"
