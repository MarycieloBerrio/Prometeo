"""What NASA PSI publishes about an investigation, kept verbatim.

These records describe the catalog (metadata, file list, publications). They are not evidence:
a `CatalogFile` means "this file exists at PSI", and nothing here is unit-normalized. Curated
trials are a separate, reviewed layer (`prometeo.domain.experiments`).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True, slots=True)
class CatalogFile:
    file_name: str
    remote_path: str  # PSI path, unique per file; the natural key of a file
    category: str | None = None  # PSI folder: Reports | Science Documents | Raw Data | ...
    subcategory: str | None = None
    size_bytes: int | None = None
    remote_url: str | None = None
    resource_id: str | None = None  # PSI resource id; shared by all files of one PSI resource
    version: int | None = None
    restricted: bool = False

    @property
    def extension(self) -> str:
        _, dot, ext = self.file_name.rpartition(".")
        return ext.lower() if dot else ""


@dataclass(frozen=True, slots=True)
class CatalogPublication:
    title: str
    authors: str | None = None
    doi: str | None = None
    status: str | None = None


@dataclass(frozen=True, slots=True)
class CatalogHit:
    """One search result: enough to decide whether to load the full investigation."""

    accession: str
    title: str
    acronym: str | None = None
    research_area: str | None = None


@dataclass(frozen=True, slots=True)
class CatalogInvestigation:
    accession: str  # PSI-25
    title: str
    url: str  # public PSI page of the investigation
    acronym: str | None = None  # BASS-II; many ground investigations have none
    doi: str | None = None
    version: int | None = None
    license: str | None = None
    research_area: str | None = None
    sub_research_area: str | None = None
    project_type: str | None = None
    flight_platform: str | None = None
    hardware: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    objectives: str | None = None
    approach: str | None = None
    hypothesis: str | None = None
    research_impacts: str | None = None
    related_accessions: tuple[str, ...] = ()
    files: tuple[CatalogFile, ...] = ()
    tables: tuple[CatalogFile, ...] = ()  # experimental tables (CSV)
    publications: tuple[CatalogPublication, ...] = ()
    extra: Mapping[str, str] = field(default_factory=dict)  # remaining PSI fields, verbatim

    @property
    def code(self) -> str:
        """Short name used across Prometeo: the acronym, or the accession when PSI gives none."""
        return self.acronym or self.accession

    @property
    def citation(self) -> str:
        version = f", version {self.version}" if self.version is not None else ""
        return f"NASA PSI {self.accession} ({self.code}): {self.title}{version}"

    def narrative_sections(self) -> tuple[tuple[str, str], ...]:
        """The free-text fields PSI publishes, as (section name, text). Empty ones are omitted."""
        candidates = (
            ("Objectives", self.objectives),
            ("Approach", self.approach),
            ("Hypothesis", self.hypothesis),
            ("Research impacts", self.research_impacts),
        )
        return tuple((name, text.strip()) for name, text in candidates if text and text.strip())
