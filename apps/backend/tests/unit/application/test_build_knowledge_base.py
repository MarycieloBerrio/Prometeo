"""BuildKnowledgeBase with in-memory fakes. All catalog content below is INVENTED test data
(accessions TEST-*), not NASA records."""

from __future__ import annotations

from collections.abc import Sequence

from prometeo.application.ports.outbound import (
    DownloadedFile,
    ExtractedPage,
    KnowledgeChunk,
    KnowledgeSource,
    KnowledgeSourceError,
    RawTableRow,
)
from prometeo.application.use_cases.build_knowledge_base import (
    BuildKnowledgeBase,
    BuildReport,
    BuildRequest,
    DocumentStatus,
    document_title,
    parse_table,
)
from prometeo.domain.knowledge.catalog import (
    CatalogFile,
    CatalogHit,
    CatalogInvestigation,
    CatalogPublication,
)


def _file(name: str, category: str, size: int = 1000, restricted: bool = False) -> CatalogFile:
    return CatalogFile(
        file_name=f"TEST-1_{category}_{name}",
        remote_path=f"/Home/psi-data/TEST-1/{category}/TEST-1_{category}_{name}",
        category=category,
        size_bytes=size,
        restricted=restricted,
    )


REPORT = _file("Final Report.pdf", "Reports")
SCAN = _file("Scanned Report.pdf", "Reports")
BROKEN = _file("Broken.pdf", "Reports")
HUGE = _file("Huge.pdf", "Reports", size=10_000_000)
LEGACY = _file("Old.doc", "Reports")
LOCKED = _file("Locked.pdf", "Reports", restricted=True)
README = _file("ReadMe.pdf", "Science Documents")
DRAWING = _file("Drawing.pdf", "Engineering Documents")
VIDEO = _file("run1.mp4", "Raw Data")
TABLE = CatalogFile(
    file_name="TEST-1_Experimental table_T.csv",
    remote_path="/Home/psi-data/TEST-1/Experimental table/TEST-1_Experimental table_T.csv",
    category="Experimental table",
)

INVESTIGATION = CatalogInvestigation(
    accession="TEST-1",
    title="Invented Solid Fuel Test",
    url="https://example.test/TEST-1",
    acronym="ISFT",
    doi="10.0000/test",
    version=3,
    license="CC0-1.0",
    research_area="Combustion Science",
    objectives="Study invented flames.",
    approach="",
    hypothesis="Invented hypothesis text.",
    related_accessions=("TEST-2",),
    files=(REPORT, SCAN, BROKEN, HUGE, LEGACY, LOCKED, README, DRAWING, VIDEO),
    tables=(TABLE,),
    publications=(CatalogPublication("An invented paper", "A. Author", "10.0000/paper"),),
)

HITS = [
    CatalogHit("TEST-1", "Invented Solid Fuel Test", "ISFT", "Combustion Science"),
    CatalogHit("TEST-9", "Invented Fluid Test", None, "Fluid Physics"),
    CatalogHit("TEST-DOWN", "Unreachable", None, "Combustion Science"),
]


class FakeCatalog:
    def __init__(self) -> None:
        self.downloads: list[str] = []

    def search(self, term: str) -> list[CatalogHit]:
        return HITS

    def get(self, accession: str) -> CatalogInvestigation:
        if accession == "TEST-DOWN":
            raise KnowledgeSourceError("HTTP 503")
        assert accession == "TEST-1"
        return INVESTIGATION

    def download(self, accession: str, file: CatalogFile) -> DownloadedFile:
        self.downloads.append(file.file_name)
        if file is TABLE:
            return DownloadedFile(b"Test #,Fuel,O2\nA1,PMMA,21\n,,\nA2,,\n", "psi/TEST-1/t.csv")
        return DownloadedFile(file.file_name.encode(), f"psi/TEST-1/{file.file_name}")


class FakeExtractor:
    def supports(self, file_name: str) -> bool:
        return file_name.endswith(".pdf")

    def extract(self, file_name: str, content: bytes) -> list[ExtractedPage]:
        if "Broken" in file_name:
            raise ValueError("not a PDF")
        if "Scanned" in file_name:
            return []
        return [
            ExtractedPage("Page one says the flame spread.", "1"),
            ExtractedPage("Page two says it went out.", "2"),
        ]


class FakeEmbedder:
    model = "fake-embedder"

    def __init__(self) -> None:
        self.inputs: list[str] = []

    def embed_passages(self, texts: Sequence[str]) -> list[list[float]]:
        self.inputs.extend(texts)
        return [[float(len(t)), 0.0] for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return [0.0, 0.0]


class MemoryStore:
    def __init__(self) -> None:
        self.investigations: list[CatalogInvestigation] = []
        self.relations: list[tuple[str, tuple[str, ...]]] = []
        self.rows: dict[str, list[RawTableRow]] = {}
        self.downloads: dict[str, tuple[str | None, str]] = {}
        self.chunks: dict[str, tuple[KnowledgeSource, list[KnowledgeChunk], str]] = {}

    def save_investigation(self, investigation: CatalogInvestigation) -> None:
        self.investigations.append(investigation)

    def link_related(self, accession: str, related: Sequence[str]) -> None:
        self.relations.append((accession, tuple(related)))

    def save_table_rows(
        self, accession: str, table: CatalogFile, rows: Sequence[RawTableRow]
    ) -> None:
        self.rows[table.file_name] = list(rows)

    def record_download(
        self, accession: str, file: CatalogFile, local_path: str | None, sha256: str
    ) -> None:
        self.downloads[file.file_name] = (local_path, sha256)

    def replace_chunks(
        self,
        accession: str,
        source: KnowledgeSource,
        chunks: Sequence[KnowledgeChunk],
        embedding_model: str,
    ) -> None:
        self.chunks[source.key] = (source, list(chunks), embedding_model)


def _report(request: BuildRequest) -> tuple[BuildReport, MemoryStore, FakeCatalog]:
    store, catalog = MemoryStore(), FakeCatalog()
    job = BuildKnowledgeBase(catalog, store, FakeEmbedder(), FakeExtractor())
    return job.execute(request), store, catalog


def _run() -> tuple[MemoryStore, FakeEmbedder]:
    store, embedder = MemoryStore(), FakeEmbedder()
    job = BuildKnowledgeBase(FakeCatalog(), store, embedder, FakeExtractor())
    job.execute(BuildRequest(term="x", research_area="Combustion Science"))
    return store, embedder


def test_only_hits_in_the_requested_research_area_are_loaded() -> None:
    report, store, _ = _report(BuildRequest(term="x", research_area="Combustion Science"))
    assert report.hits == 3
    assert report.skipped_other_area == ("TEST-9",)
    assert [i.accession for i in store.investigations] == ["TEST-1"]


def test_an_unreachable_investigation_is_reported_and_does_not_stop_the_job() -> None:
    report, store, _ = _report(BuildRequest(term="x", research_area="Combustion Science"))
    failed = report.failed
    assert [f.accession for f in failed] == ["TEST-DOWN"]
    assert failed[0].error == "HTTP 503"
    assert len(store.investigations) == 1


def test_only_filter_restricts_to_named_accessions() -> None:
    report, _, _ = _report(BuildRequest(term="x", accessions=("test-1",)))
    assert [i.accession for i in report.investigations] == ["TEST-1"]


def test_narrative_fields_are_indexed_verbatim_with_dataset_provenance() -> None:
    store, embedder = _run()
    source, chunks, model = store.chunks["psi:TEST-1:dataset"]
    assert model == "fake-embedder"
    assert source.kind == "psi_dataset"
    assert source.doi == "10.0000/test"
    assert source.url == "https://example.test/TEST-1"
    assert source.version == "3"
    assert "TEST-1" in source.reference and "version 3" in source.reference
    # The empty `approach` field produces nothing; the stored text is exactly PSI's text.
    assert [(c.section, c.text) for c in chunks] == [
        ("Objectives", "Study invented flames."),
        ("Hypothesis", "Invented hypothesis text."),
    ]
    assert [c.index for c in chunks] == [0, 1]
    # The embedding input carries context; the stored text does not.
    assert (
        embedder.inputs[0] == "ISFT — Invented Solid Fuel Test. Objectives: Study invented flames."
    )


def test_documents_are_chunked_per_page_and_linked_to_their_file() -> None:
    store, _ = _run()
    source, chunks, _ = store.chunks[f"psi:TEST-1:file:{REPORT.remote_path}"]
    assert source.title == "Final Report"
    assert source.source_file == REPORT.file_name
    assert source.file is REPORT
    assert source.evidence_role == "experimental"
    assert [(c.page, c.text) for c in chunks] == [
        ("1", "Page one says the flame spread."),
        ("2", "Page two says it went out."),
    ]
    assert len({c.id for c in chunks}) == 2
    local_path, sha256 = store.downloads[REPORT.file_name]
    assert local_path == f"psi/TEST-1/{REPORT.file_name}"
    assert len(sha256) == 64


def test_documents_that_are_not_results_are_context_not_evidence() -> None:
    store, _ = _run()
    source, _, _ = store.chunks[f"psi:TEST-1:file:{README.remote_path}"]
    assert source.evidence_role == "context"


def test_each_unindexable_document_is_reported_with_its_reason() -> None:
    report, store, catalog = _report(
        BuildRequest(term="x", accessions=("TEST-1",), max_file_bytes=1_000_000)
    )
    status = {d.file_name: d.status for d in report.investigations[0].documents}
    assert status == {
        REPORT.file_name: DocumentStatus.INDEXED,
        SCAN.file_name: DocumentStatus.NO_TEXT,
        BROKEN.file_name: DocumentStatus.FAILED,
        HUGE.file_name: DocumentStatus.TOO_LARGE,
        LEGACY.file_name: DocumentStatus.UNSUPPORTED,
        LOCKED.file_name: DocumentStatus.RESTRICTED,
        README.file_name: DocumentStatus.INDEXED,
    }
    # Files outside the requested folders are catalogued but never downloaded.
    assert DRAWING.file_name not in catalog.downloads
    assert VIDEO.file_name not in catalog.downloads
    for skipped in (HUGE, LEGACY, LOCKED):
        assert skipped.file_name not in catalog.downloads
    # A scan leaves no chunks behind.
    assert store.chunks[f"psi:TEST-1:file:{SCAN.remote_path}"][1] == []


def test_no_documents_flag_indexes_metadata_only() -> None:
    report, store, catalog = _report(
        BuildRequest(term="x", accessions=("TEST-1",), index_documents=False)
    )
    assert report.investigations[0].documents == ()
    assert list(store.chunks) == ["psi:TEST-1:dataset"]
    assert catalog.downloads == [TABLE.file_name]


def test_table_rows_are_stored_verbatim_and_never_become_trials() -> None:
    store, _ = _run()
    rows = store.rows[TABLE.file_name]
    assert [(r.row_number, r.test_label, dict(r.data)) for r in rows] == [
        (1, "A1", {"Test #": "A1", "Fuel": "PMMA", "O2": "21"}),
        (3, "A2", {"Test #": "A2", "Fuel": "", "O2": ""}),  # blanks stay blank; row 2 was empty
    ]


def test_relations_are_linked_after_all_investigations_are_saved() -> None:
    store, _ = _run()
    assert store.relations == [("TEST-1", ("TEST-2",))]


def test_report_totals() -> None:
    report, _, _ = _report(BuildRequest(term="x", accessions=("TEST-1",)))
    outcome = report.investigations[0]
    assert outcome.files_catalogued == 10
    assert outcome.publications == 1
    assert outcome.table_rows == 2
    assert outcome.metadata_chunks == 2
    # Three readable PDFs (the 10 MB one is under the default size limit), two pages each.
    assert outcome.document_chunks == 6
    assert report.total_chunks == 8
    assert report.embedding_model == "fake-embedder"


def test_parse_table_handles_bom_duplicate_headers_and_ragged_rows() -> None:
    rows = parse_table("﻿Test #,O2,O2,\nB1,21,20.9,note,extra\n".encode())
    assert dict(rows[0].data) == {
        "Test #": "B1",
        "O2": "21",
        "O2 (2)": "20.9",
        "column 4": "note",
        "column 5": "extra",
    }
    assert rows[0].test_label == "B1"
    assert parse_table(b"") == []


def test_parse_table_has_no_label_when_no_test_column_exists() -> None:
    rows = parse_table(b"Run,Fuel\n7,PMMA\n")
    assert rows[0].test_label is None


def test_document_title_strips_the_psi_prefix() -> None:
    assert document_title("TEST-1", REPORT) == "Final Report"
    bare = CatalogFile(file_name="notes.pdf", remote_path="/x/notes.pdf")
    assert document_title("TEST-1", bare) == "notes"
