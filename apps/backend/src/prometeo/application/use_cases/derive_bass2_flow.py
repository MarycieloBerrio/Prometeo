"""Derive BASS-II flow speeds from the PSI-25 experimental table (offline curation aid).

The output is a worksheet for the curator, not evidence: every speed is `derived`, carries its
method, and still has to be reviewed before it is used in a curated trial. Tests whose flow was
changed during the burn give one speed per step; matching each step to a measured spread rate is
human curation and is not attempted here.
"""

from __future__ import annotations

from dataclasses import dataclass

from prometeo.application.ports.outbound import InvestigationCatalog, KnowledgeSourceError
from prometeo.application.use_cases.build_knowledge_base import parse_table
from prometeo.domain.physics.fan_calibration import (
    BASS2_FLOW_METHOD,
    FlowDerivation,
    FlowDerivationKind,
    derive_bass2_flow,
)

BASS2_ACCESSION = "PSI-25"
_AIR_DISPLAY = "Air display"
_COLUMNS = {
    "pi": "PI",
    "material": "Fuel Sample Material",
    "sample": "Sample #",
    "restrictors": "Flow restrictor",
    "fan_display": "Fan display",
}


@dataclass(frozen=True, slots=True)
class TestFlow:
    """One row of the PSI-25 table with its derived flow. Raw cells are kept verbatim."""

    __test__ = False  # not a pytest class, despite the name

    row_number: int
    test_label: str | None
    pi: str | None
    material: str | None
    sample: str | None
    restrictors: str | None
    fan_display: str | None
    air_display: str
    derivation: FlowDerivation


@dataclass(frozen=True, slots=True)
class Bass2FlowReport:
    citation: str
    doi: str | None
    url: str
    table_file: str
    method: str
    tests: tuple[TestFlow, ...]

    def count(self, kind: FlowDerivationKind) -> int:
        return sum(t.derivation.kind is kind for t in self.tests)


class DeriveBass2FlowSpeeds:
    def __init__(self, catalog: InvestigationCatalog) -> None:
        self._catalog = catalog

    def execute(self) -> Bass2FlowReport:
        investigation = self._catalog.get(BASS2_ACCESSION)
        table = next((t for t in investigation.tables if t.extension == "csv"), None)
        if table is None:
            raise KnowledgeSourceError(f"{BASS2_ACCESSION} has no CSV experimental table")
        rows = parse_table(self._catalog.download(BASS2_ACCESSION, table).content)
        if rows and _AIR_DISPLAY not in rows[0].data:
            raise KnowledgeSourceError(
                f"the {BASS2_ACCESSION} table has no '{_AIR_DISPLAY}' column; its layout changed"
            )
        tests = tuple(
            TestFlow(
                row_number=row.row_number,
                test_label=row.test_label,
                air_display=row.data[_AIR_DISPLAY],
                derivation=derive_bass2_flow(row.data[_AIR_DISPLAY]),
                **{
                    field: row.data.get(column, "").strip() or None
                    for field, column in _COLUMNS.items()
                },
            )
            for row in rows
        )
        return Bass2FlowReport(
            citation=investigation.citation,
            doi=investigation.doi,
            url=investigation.url,
            table_file=table.file_name,
            method=BASS2_FLOW_METHOD,
            tests=tests,
        )
