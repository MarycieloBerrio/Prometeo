"""DeriveBass2FlowSpeeds with a fake catalog. Table content is INVENTED test data."""

from __future__ import annotations

import pytest

from prometeo.application.ports.outbound import DownloadedFile, KnowledgeSourceError
from prometeo.application.use_cases.derive_bass2_flow import DeriveBass2FlowSpeeds
from prometeo.domain.knowledge.catalog import CatalogFile, CatalogHit, CatalogInvestigation
from prometeo.domain.physics.fan_calibration import FlowDerivationKind

TABLE = CatalogFile(file_name="t.csv", remote_path="/x/t.csv", category="Experimental table")
CSV = (
    b"PI,Test #,Sample #,Fuel Sample Material,Flow restrictor,Fan display,Air display\n"
    b"Tester,X1,1,invented film,2,62,5\n"
    b"Tester,X2,2,invented rod,2,,10  5  1\n"
    b"Tester,X3,3,invented rod,0,47,10   blowoff\n"
    b"Tester,X4,4,,2,,\n"
)


class FakeCatalog:
    def __init__(self, csv: bytes = CSV, tables: tuple[CatalogFile, ...] = (TABLE,)) -> None:
        self._csv = csv
        self._tables = tables

    def search(self, term: str) -> list[CatalogHit]:
        return []

    def get(self, accession: str) -> CatalogInvestigation:
        assert accession == "PSI-25"
        return CatalogInvestigation(
            accession="PSI-25",
            title="Invented",
            url="https://example.test/PSI-25",
            acronym="TEST",
            doi="10.0000/test",
            version=1,
            tables=self._tables,
        )

    def download(self, accession: str, file: CatalogFile) -> DownloadedFile:
        return DownloadedFile(self._csv)


def test_each_row_is_classified_and_raw_cells_are_kept() -> None:
    report = DeriveBass2FlowSpeeds(FakeCatalog()).execute()
    kinds = {t.test_label: t.derivation.kind for t in report.tests}
    assert kinds == {
        "X1": FlowDerivationKind.SINGLE,
        "X2": FlowDerivationKind.STEPPED,
        "X3": FlowDerivationKind.NOT_DERIVABLE,
        "X4": FlowDerivationKind.NOT_DERIVABLE,
    }
    x1, x2, x3, x4 = report.tests
    assert [q.value for q in x1.derivation.speeds] == [5.033]
    assert x1.material == "invented film" and x1.restrictors == "2" and x1.fan_display == "62"
    assert [q.value for q in x2.derivation.speeds] == [10.066, 5.033]  # the "1" is not converted
    assert x2.fan_display is None  # blank stays unknown
    assert x3.air_display == "10   blowoff"  # verbatim
    assert x4.material is None
    assert report.count(FlowDerivationKind.NOT_DERIVABLE) == 2


def test_report_carries_provenance_and_method() -> None:
    report = DeriveBass2FlowSpeeds(FakeCatalog()).execute()
    assert "PSI-25" in report.citation
    assert report.doi == "10.0000/test"
    assert report.table_file == "t.csv"
    assert "1.0066" in report.method


def test_a_changed_table_layout_is_an_error_not_a_guess() -> None:
    with pytest.raises(KnowledgeSourceError, match="Air display"):
        DeriveBass2FlowSpeeds(FakeCatalog(csv=b"Test #,Flow\nX1,5\n")).execute()


def test_missing_table_is_an_error() -> None:
    with pytest.raises(KnowledgeSourceError, match="no CSV"):
        DeriveBass2FlowSpeeds(FakeCatalog(tables=())).execute()
