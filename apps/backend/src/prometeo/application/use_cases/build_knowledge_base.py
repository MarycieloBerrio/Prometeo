"""Build the Research Assistant's knowledge base from the NASA PSI repository.

This is an OFFLINE preparation job (never run per request). For every investigation matching a
search term it:

  1. stores the catalog verbatim: investigation metadata, publications, the list of files
     (not the files themselves) and the rows of the experimental table;
  2. indexes text for retrieval: the narrative fields PSI publishes (objectives, approach,
     hypothesis, research impacts) and, optionally, the investigation's documents.

Integrity rules that hold here:
  - Nothing is invented or filled. Text is chunked verbatim; table cells stay text.
  - Table rows are NOT turned into trials. That is reviewed curation (see data/README.md).
  - A document with no extractable text (a scan) is reported as such; there is no OCR guess.
  - Every chunk points to a source with a citation, URL and, for documents, the page.
"""

from __future__ import annotations

import csv
import hashlib
import io
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum

from prometeo.application.ports.outbound import (
    InvestigationCatalog,
    KnowledgeChunk,
    KnowledgeSource,
    KnowledgeSourceError,
    KnowledgeStore,
    RawTableRow,
    TextEmbedder,
    TextExtractor,
)
from prometeo.domain.knowledge.catalog import CatalogFile, CatalogInvestigation
from prometeo.domain.knowledge.chunking import chunk_text

DEFAULT_DOCUMENT_CATEGORIES = ("Reports", "Science Documents")
DEFAULT_MAX_FILE_BYTES = 60 * 1024 * 1024

# PSI folders whose documents report results. Everything else (requirements, drawings, crew
# training, presentations) is indexed as context: it can be quoted, it is never evidence.
# TODO(science): confirm with the science lead whether "Science Documents" (requirements,
# ReadMe files) should count as experimental. Left as context, the conservative choice.
_EXPERIMENTAL_CATEGORIES = frozenset({"Reports", "Analyzed Data"})
_TEST_LABEL_HEADERS = frozenset({"test #", "test number", "test id", "test"})
_SLUG = re.compile(r"[^a-z0-9]+")


class DocumentStatus(StrEnum):
    INDEXED = "indexed"
    NO_TEXT = "no_extractable_text"
    UNSUPPORTED = "unsupported_format"
    TOO_LARGE = "too_large"
    RESTRICTED = "restricted"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class BuildRequest:
    term: str
    research_area: str | None = None  # keep only hits in this PSI research area
    accessions: tuple[str, ...] = ()  # keep only these (e.g. ("PSI-25",)); empty = all hits
    index_documents: bool = True
    document_categories: tuple[str, ...] = DEFAULT_DOCUMENT_CATEGORIES
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES


@dataclass(frozen=True, slots=True)
class DocumentOutcome:
    file_name: str
    status: DocumentStatus
    chunks: int = 0
    detail: str | None = None


@dataclass(frozen=True, slots=True)
class InvestigationOutcome:
    accession: str
    code: str
    files_catalogued: int = 0
    publications: int = 0
    table_rows: int = 0
    metadata_chunks: int = 0
    documents: tuple[DocumentOutcome, ...] = ()
    error: str | None = None  # set when the investigation could not be loaded at all

    @property
    def document_chunks(self) -> int:
        return sum(d.chunks for d in self.documents)


@dataclass(frozen=True, slots=True)
class BuildReport:
    term: str
    hits: int
    skipped_other_area: tuple[str, ...]
    investigations: tuple[InvestigationOutcome, ...]
    embedding_model: str

    @property
    def total_chunks(self) -> int:
        return sum(i.metadata_chunks + i.document_chunks for i in self.investigations)

    @property
    def failed(self) -> tuple[InvestigationOutcome, ...]:
        return tuple(i for i in self.investigations if i.error)


Progress = Callable[[str], None]


class BuildKnowledgeBase:
    def __init__(
        self,
        catalog: InvestigationCatalog,
        store: KnowledgeStore,
        embedder: TextEmbedder,
        extractor: TextExtractor,
    ) -> None:
        self._catalog = catalog
        self._store = store
        self._embedder = embedder
        self._extractor = extractor

    def execute(self, request: BuildRequest, progress: Progress | None = None) -> BuildReport:
        say = progress or (lambda _message: None)
        hits = self._catalog.search(request.term)
        wanted = {a.upper() for a in request.accessions}
        selected: list[str] = []
        other_area: list[str] = []
        for hit in hits:
            if wanted and hit.accession.upper() not in wanted:
                continue
            if request.research_area and hit.research_area != request.research_area:
                other_area.append(hit.accession)
                continue
            selected.append(hit.accession)

        outcomes: list[InvestigationOutcome] = []
        loaded: list[CatalogInvestigation] = []
        for position, accession in enumerate(selected, start=1):
            say(f"[{position}/{len(selected)}] {accession}")
            try:
                investigation = self._catalog.get(accession)
            except KnowledgeSourceError as exc:
                say(f"  could not load {accession}: {exc}")
                outcomes.append(InvestigationOutcome(accession, accession, error=str(exc)))
                continue
            outcomes.append(self._ingest(investigation, request, say))
            loaded.append(investigation)

        # Relations go last: both ends must already be in the store.
        for investigation in loaded:
            if investigation.related_accessions:
                self._store.link_related(investigation.accession, investigation.related_accessions)

        return BuildReport(
            term=request.term,
            hits=len(hits),
            skipped_other_area=tuple(other_area),
            investigations=tuple(outcomes),
            embedding_model=self._embedder.model,
        )

    # ── one investigation ────────────────────────────────────────────────────────────────

    def _ingest(
        self, inv: CatalogInvestigation, request: BuildRequest, say: Progress
    ) -> InvestigationOutcome:
        self._store.save_investigation(inv)
        table_rows = sum(self._ingest_table(inv, table, say) for table in inv.tables)
        metadata_chunks = self._index_metadata(inv)

        documents: list[DocumentOutcome] = []
        if request.index_documents:
            categories = set(request.document_categories)
            for file in inv.files:
                if file.category in categories:
                    outcome = self._index_document(inv, file, request.max_file_bytes)
                    say(
                        f"  {outcome.status.value:<20} {outcome.chunks:>4} chunks  {file.file_name}"
                    )
                    documents.append(outcome)

        return InvestigationOutcome(
            accession=inv.accession,
            code=inv.code,
            files_catalogued=len(inv.files) + len(inv.tables),
            publications=len(inv.publications),
            table_rows=table_rows,
            metadata_chunks=metadata_chunks,
            documents=tuple(documents),
        )

    def _ingest_table(self, inv: CatalogInvestigation, table: CatalogFile, say: Progress) -> int:
        if table.extension != "csv":
            say(f"  table skipped (not CSV): {table.file_name}")
            return 0
        try:
            downloaded = self._catalog.download(inv.accession, table)
        except KnowledgeSourceError as exc:
            say(f"  table not downloaded: {table.file_name}: {exc}")
            return 0
        rows = parse_table(downloaded.content)
        self._store.record_download(
            inv.accession, table, downloaded.local_path, _sha256(downloaded.content)
        )
        self._store.save_table_rows(inv.accession, table, rows)
        return len(rows)

    def _index_metadata(self, inv: CatalogInvestigation) -> int:
        source = KnowledgeSource(
            key=dataset_source_key(inv.accession),
            kind="psi_dataset",
            evidence_role="experimental",
            reference=inv.citation,
            title=inv.title,
            url=inv.url,
            doi=inv.doi,
            version=str(inv.version) if inv.version is not None else None,
            license=inv.license,
        )
        prefix = _slug(inv.accession)
        pieces: list[tuple[str, str, str]] = []  # (id, section, text)
        for section, text in inv.narrative_sections():
            for n, chunk in enumerate(chunk_text(text)):
                pieces.append((f"{prefix}-meta-{_slug(section)}-{n}", section, chunk))
        chunks = self._embed(
            [(chunk_id, text, None, section) for chunk_id, section, text in pieces],
            # The investigation title gives short fields ("Objectives: …") their subject.
            context=f"{inv.code} — {inv.title}",
        )
        self._store.replace_chunks(inv.accession, source, chunks, self._embedder.model)
        return len(chunks)

    def _index_document(
        self, inv: CatalogInvestigation, file: CatalogFile, max_bytes: int
    ) -> DocumentOutcome:
        name = file.file_name
        if file.restricted:
            return DocumentOutcome(name, DocumentStatus.RESTRICTED)
        if not self._extractor.supports(name):
            return DocumentOutcome(name, DocumentStatus.UNSUPPORTED, detail=file.extension)
        if file.size_bytes is not None and file.size_bytes > max_bytes:
            size_mb = file.size_bytes / 1024 / 1024
            return DocumentOutcome(name, DocumentStatus.TOO_LARGE, detail=f"{size_mb:.0f} MB")
        try:
            downloaded = self._catalog.download(inv.accession, file)
            self._store.record_download(
                inv.accession, file, downloaded.local_path, _sha256(downloaded.content)
            )
            pages = self._extractor.extract(name, downloaded.content)
        except Exception as exc:  # a broken PDF must not stop the whole job
            return DocumentOutcome(
                name, DocumentStatus.FAILED, detail=f"{type(exc).__name__}: {exc}"
            )

        title = document_title(inv.accession, file)
        prefix = f"{_slug(inv.accession)}-{_slug(title)[:60]}-{_short_hash(file.remote_path)}"
        pieces: list[tuple[str, str, str | None, str | None]] = []
        for page in pages:
            for chunk in chunk_text(page.text):
                page_part = f"p{_slug(page.page)}-" if page.page else ""
                pieces.append((f"{prefix}-{page_part}{len(pieces)}", chunk, page.page, None))
        if not pieces:
            # Scanned or image-only file. Say so; do not pretend it was indexed.
            self._store.replace_chunks(
                inv.accession, _document_source(inv, file, title), [], self._embedder.model
            )
            return DocumentOutcome(name, DocumentStatus.NO_TEXT)

        chunks = self._embed(pieces, context=f"{inv.code} — {title}")
        self._store.replace_chunks(
            inv.accession, _document_source(inv, file, title), chunks, self._embedder.model
        )
        return DocumentOutcome(name, DocumentStatus.INDEXED, chunks=len(chunks))

    def _embed(
        self, pieces: Sequence[tuple[str, str, str | None, str | None]], context: str
    ) -> list[KnowledgeChunk]:
        """Embed `context + section + text`; store only the verbatim text."""
        if not pieces:
            return []
        inputs = [
            f"{context}. {section}: {text}" if section else f"{context}. {text}"
            for _id, text, _page, section in pieces
        ]
        vectors = self._embedder.embed_passages(inputs)
        if len(vectors) != len(pieces):
            raise RuntimeError("embedder returned a different number of vectors than texts")
        return [
            KnowledgeChunk(
                id=chunk_id, index=i, text=text, embedding=vector, page=page, section=section
            )
            for i, ((chunk_id, text, page, section), vector) in enumerate(
                zip(pieces, vectors, strict=True)
            )
        ]


# ── pure helpers ─────────────────────────────────────────────────────────────────────────


def dataset_source_key(accession: str) -> str:
    return f"psi:{accession}:dataset"


def publication_source_key(accession: str, doi: str | None, title: str) -> str:
    identity = doi.lower() if doi else _short_hash(title.strip().lower())
    return f"psi:{accession}:publication:{identity}"


def file_source_key(accession: str, file: CatalogFile) -> str:
    return f"psi:{accession}:file:{file.remote_path}"


def document_title(accession: str, file: CatalogFile) -> str:
    """`PSI-25_Reports_BASS-II Summary Report.pdf` → `BASS-II Summary Report`."""
    stem = file.file_name.rsplit(".", 1)[0] if "." in file.file_name else file.file_name
    leads = [f"{accession}_"]
    if file.category:
        leads.insert(0, f"{accession}_{file.category}_")
    for lead in leads:
        if stem.startswith(lead):
            return stem[len(lead) :].strip() or stem
    return stem


def parse_table(content: bytes) -> list[RawTableRow]:
    """Read a PSI experimental table (CSV) into verbatim rows keyed by column header.

    Cells are kept as text, exactly as published: no numeric parsing, no unit handling, no
    filling of blanks. Rows that are entirely empty are dropped.
    """
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("cp1252", errors="replace")
    reader = csv.reader(io.StringIO(text, newline=""))
    try:
        raw_header = next(reader)
    except StopIteration:
        return []
    header = _unique_headers(raw_header)
    label_column = next((h for h in header if h.strip().lower() in _TEST_LABEL_HEADERS), None)
    rows: list[RawTableRow] = []
    for number, cells in enumerate(reader, start=1):
        if not any(cell.strip() for cell in cells):
            continue
        padded = [*cells, *[""] * (len(header) - len(cells))]
        data = dict(zip(header, padded, strict=False))
        for extra_index, extra in enumerate(cells[len(header) :], start=len(header) + 1):
            data[f"column {extra_index}"] = extra  # more cells than headers: keep them
        label = data.get(label_column, "").strip() if label_column else ""
        rows.append(RawTableRow(row_number=number, data=data, test_label=label or None))
    return rows


def _unique_headers(raw: Sequence[str]) -> list[str]:
    seen: dict[str, int] = {}
    out: list[str] = []
    for position, name in enumerate(raw, start=1):
        name = name.strip() or f"column {position}"
        seen[name] = seen.get(name, 0) + 1
        out.append(name if seen[name] == 1 else f"{name} ({seen[name]})")
    return out


def _document_source(inv: CatalogInvestigation, file: CatalogFile, title: str) -> KnowledgeSource:
    role = "experimental" if file.category in _EXPERIMENTAL_CATEGORIES else "context"
    return KnowledgeSource(
        key=file_source_key(inv.accession, file),
        kind="report",
        evidence_role=role,
        reference=f"{title} — {inv.citation}",
        title=title,
        url=inv.url,
        doi=inv.doi,
        source_file=file.file_name,
        version=str(file.version) if file.version is not None else None,
        license=inv.license,
        file=file,
    )


def _slug(value: str) -> str:
    return _SLUG.sub("-", value.lower()).strip("-")


def _short_hash(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8"), usedforsecurity=False).hexdigest()[:8]


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()
