"""Outbound (driven) ports. Adapters in `prometeo.adapters.outbound` implement these.

Ports speak domain types only — never ORM rows, HTTP payloads or vendor SDK objects.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Protocol

from prometeo.domain.experiments.filters import TrialFilter
from prometeo.domain.experiments.model import Provenance, Trial
from prometeo.domain.flamevision.model import Calibration, FlameFrontTrack
from prometeo.domain.knowledge.catalog import CatalogFile, CatalogHit, CatalogInvestigation


class TrialRepository(Protocol):
    def get(self, trial_id: str) -> Trial | None: ...
    def search(self, criteria: TrialFilter) -> list[Trial]: ...
    def list_all(self) -> list[Trial]: ...


@dataclass(frozen=True, slots=True)
class DocumentChunk:
    id: str
    text: str
    provenance: Provenance
    score: float = 0.0


class DocumentRetriever(Protocol):
    """Hybrid (text + vector) retrieval over pre-indexed NASA documents."""

    def retrieve(self, query: str, limit: int = 8) -> list[DocumentChunk]: ...


@dataclass(frozen=True, slots=True)
class EvidencePacket:
    """Everything the explanation model may use. It must not add facts beyond this."""

    question: str
    trials: Sequence[Trial]
    computed_facts: Sequence[str]
    documents: Sequence[DocumentChunk]
    limitations: Sequence[str] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class Explanation:
    text: str
    cited_sources: tuple[str, ...]
    model: str


class ExplanationGenerator(Protocol):
    """Writes the narrative. Runs LAST, after retrieval, validation and computation."""

    def explain(self, packet: EvidencePacket) -> Explanation: ...


class FlameFrontDetector(Protocol):
    def track(
        self, trial_id: str, video_uri: str, calibration: Calibration
    ) -> FlameFrontTrack: ...


# ───────────────────────── Knowledge base (offline preparation job) ─────────────────────────


class KnowledgeSourceError(Exception):
    """The upstream catalog could not be read (network error, unexpected payload, HTTP error)."""


@dataclass(frozen=True, slots=True)
class DownloadedFile:
    content: bytes
    local_path: str | None = None  # relative to data/raw/ when the adapter keeps a copy


class InvestigationCatalog(Protocol):
    """A repository of investigations published by NASA (PSI). Read-only."""

    def search(self, term: str) -> list[CatalogHit]: ...
    def get(self, accession: str) -> CatalogInvestigation: ...
    def download(self, accession: str, file: CatalogFile) -> DownloadedFile: ...


@dataclass(frozen=True, slots=True)
class ExtractedPage:
    text: str
    page: str | None = None  # page or slide label as it appears in the file


class TextExtractor(Protocol):
    """Pulls the text out of a document, page by page. No OCR, no interpretation."""

    def supports(self, file_name: str) -> bool: ...
    def extract(self, file_name: str, content: bytes) -> list[ExtractedPage]: ...


class TextEmbedder(Protocol):
    @property
    def model(self) -> str: ...
    def embed_passages(self, texts: Sequence[str]) -> list[list[float]]: ...
    def embed_query(self, text: str) -> list[float]: ...


@dataclass(frozen=True, slots=True)
class KnowledgeSource:
    """Something citable that chunks are attached to (a PSI dataset or one of its documents)."""

    key: str  # stable natural key, e.g. psi:PSI-25:dataset — makes re-runs idempotent
    kind: str  # psi_dataset | report | publication
    evidence_role: str  # experimental | context
    reference: str  # human-readable citation
    title: str | None = None
    url: str | None = None
    doi: str | None = None
    source_file: str | None = None
    version: str | None = None
    license: str | None = None
    file: CatalogFile | None = None  # the catalogued PSI file, when the source is one


@dataclass(frozen=True, slots=True)
class KnowledgeChunk:
    id: str
    index: int
    text: str
    embedding: Sequence[float]
    page: str | None = None
    section: str | None = None


@dataclass(frozen=True, slots=True)
class RawTableRow:
    """One row of a PSI experimental table, exactly as published (cells are text)."""

    row_number: int
    data: Mapping[str, str]
    test_label: str | None = None


class KnowledgeStore(Protocol):
    """Write side of the evidence store's catalog and retrieval layers."""

    def save_investigation(self, investigation: CatalogInvestigation) -> None: ...
    def link_related(self, accession: str, related: Sequence[str]) -> None: ...
    def save_table_rows(
        self, accession: str, table: CatalogFile, rows: Sequence[RawTableRow]
    ) -> None: ...
    def record_download(
        self, accession: str, file: CatalogFile, local_path: str | None, sha256: str
    ) -> None: ...
    def replace_chunks(
        self,
        accession: str,
        source: KnowledgeSource,
        chunks: Sequence[KnowledgeChunk],
        embedding_model: str,
    ) -> None: ...
