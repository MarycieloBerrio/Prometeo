"""Scientific rules for CompareTrials: withhold causal deltas unless DIRECT."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from prometeo.adapters.outbound.persistence.json_trial_repository import JsonTrialRepository
from prometeo.application.use_cases.compare_trials import CompareTrials
from prometeo.domain.experiments.filters import TrialFilter
from prometeo.domain.experiments.model import (
    DataQuality,
    FlowDirection,
    GeometryType,
    Measurement,
    Trial,
    Ventilation,
)
from prometeo.domain.physics.compatibility import Comparability, Variable
from prometeo.domain.shared.quantity import Quantity
from tests.factories import TEST_PROV, make_trial

_CURATED = Path(__file__).resolve().parents[5] / "data" / "curated" / "trials.json"


class _Repo:
    def __init__(self, trials: list[Trial]) -> None:
        self._by_id = {t.id: t for t in trials}

    def get(self, trial_id: str) -> Trial | None:
        return self._by_id.get(trial_id)

    def search(self, criteria: TrialFilter) -> list[Trial]:
        return [t for t in self._by_id.values() if criteria.matches(t)]

    def list_all(self) -> list[Trial]:
        return list(self._by_id.values())


def _pair_flow_only() -> tuple[Trial, Trial]:
    a = make_trial("A")
    b = make_trial("B", ventilation=Ventilation(Quantity(10, "cm/s"), FlowDirection.CONCURRENT))
    return a, b


def test_direct_comparison_returns_unit_correct_delta() -> None:
    a, b = _pair_flow_only()
    b = replace(
        b,
        results=(
            Measurement(
                "flame_spread_rate",
                Quantity(1.5, "mm/s"),
                DataQuality.MEASURED,
                TEST_PROV,
            ),
        ),
    )
    result = CompareTrials(_Repo([a, b])).execute(
        "A", "B", frozenset({Variable.FLOW_SPEED}), ["flame_spread_rate"]
    )
    assert result.compatibility.level is Comparability.DIRECT
    assert result.withheld_reason is None
    assert len(result.deltas) == 1
    assert result.deltas[0].difference.unit == "mm/s"
    assert result.deltas[0].difference.value == 0.5


def test_partial_unknown_pressure_withholds_deltas() -> None:
    a = make_trial("A", pressure=None)
    b = make_trial(
        "B",
        pressure=None,
        ventilation=Ventilation(Quantity(10, "cm/s"), FlowDirection.CONCURRENT),
        results=(
            Measurement(
                "flame_spread_rate",
                Quantity(1.5, "mm/s"),
                DataQuality.MEASURED,
                TEST_PROV,
            ),
        ),
    )
    result = CompareTrials(_Repo([a, b])).execute(
        "A", "B", frozenset({Variable.FLOW_SPEED}), ["flame_spread_rate"]
    )
    assert result.compatibility.level is Comparability.PARTIAL
    assert result.deltas == ()
    assert result.withheld_reason
    assert "partially comparable" in result.withheld_reason.lower()


def test_unknown_oxygen_blocks_causal_flow_delta() -> None:
    a = make_trial("A", oxygen=None)
    b = make_trial(
        "B",
        oxygen=None,
        ventilation=Ventilation(Quantity(10, "cm/s"), FlowDirection.CONCURRENT),
        results=(
            Measurement(
                "flame_spread_rate",
                Quantity(2.0, "mm/s"),
                DataQuality.MEASURED,
                TEST_PROV,
            ),
        ),
    )
    result = CompareTrials(_Repo([a, b])).execute(
        "A", "B", frozenset({Variable.FLOW_SPEED}), ["flame_spread_rate"]
    )
    assert result.compatibility.level is Comparability.PARTIAL
    assert result.deltas == ()
    assert result.withheld_reason


def test_geometry_mismatch_not_comparable_no_deltas() -> None:
    a = make_trial("A")
    b = make_trial(
        "B",
        geometry=replace(a.geometry, type=GeometryType.CYLINDER),
        ventilation=Ventilation(Quantity(10, "cm/s"), FlowDirection.CONCURRENT),
    )
    result = CompareTrials(_Repo([a, b])).execute(
        "A", "B", frozenset({Variable.FLOW_SPEED}), ["flame_spread_rate"]
    )
    assert result.compatibility.level is Comparability.NOT_COMPARABLE
    assert result.deltas == ()
    assert result.withheld_reason


def test_opposed_vs_concurrent_no_deltas() -> None:
    a = make_trial("A", ventilation=Ventilation(Quantity(5, "cm/s"), FlowDirection.OPPOSED))
    b = make_trial("B", ventilation=Ventilation(Quantity(5, "cm/s"), FlowDirection.CONCURRENT))
    result = CompareTrials(_Repo([a, b])).execute(
        "A", "B", frozenset({Variable.OXYGEN}), ["flame_spread_rate"]
    )
    assert result.compatibility.level is Comparability.NOT_COMPARABLE
    assert result.deltas == ()


def test_incompatible_metric_units_skip_without_inventing_number() -> None:
    a = make_trial("A")
    b = make_trial(
        "B",
        ventilation=Ventilation(Quantity(10, "cm/s"), FlowDirection.CONCURRENT),
        results=(
            Measurement(
                "flame_spread_rate",
                Quantity(1.5, "kPa"),  # wrong dimension on purpose
                DataQuality.MEASURED,
                TEST_PROV,
            ),
        ),
    )
    result = CompareTrials(_Repo([a, b])).execute(
        "A", "B", frozenset({Variable.FLOW_SPEED}), ["flame_spread_rate"]
    )
    assert result.compatibility.level is Comparability.DIRECT
    assert result.deltas == ()
    assert result.withheld_reason
    assert "units" in result.withheld_reason.lower()


def test_extracted_pair_does_not_produce_evidence_delta() -> None:
    a = make_trial(
        "A",
        results=(
            Measurement(
                "flame_spread_rate",
                Quantity(1.0, "mm/s"),
                DataQuality.EXTRACTED,
                TEST_PROV,
            ),
        ),
    )
    b = make_trial(
        "B",
        ventilation=Ventilation(Quantity(10, "cm/s"), FlowDirection.CONCURRENT),
        results=(
            Measurement(
                "flame_spread_rate",
                Quantity(1.5, "mm/s"),
                DataQuality.EXTRACTED,
                TEST_PROV,
            ),
        ),
    )
    result = CompareTrials(_Repo([a, b])).execute(
        "A", "B", frozenset({Variable.FLOW_SPEED}), ["flame_spread_rate"]
    )
    assert result.compatibility.level is Comparability.DIRECT
    assert result.deltas == ()
    assert result.withheld_reason
    assert "extracted" in result.withheld_reason.lower()


def test_derived_without_method_does_not_produce_evidence_delta() -> None:
    a = make_trial("A")
    b = make_trial(
        "B",
        ventilation=Ventilation(Quantity(10, "cm/s"), FlowDirection.CONCURRENT),
        results=(
            Measurement(
                "flame_spread_rate",
                Quantity(1.5, "mm/s"),
                DataQuality.DERIVED,
                TEST_PROV,
                method=None,
            ),
        ),
    )
    result = CompareTrials(_Repo([a, b])).execute(
        "A", "B", frozenset({Variable.FLOW_SPEED}), ["flame_spread_rate"]
    )
    assert result.compatibility.level is Comparability.DIRECT
    assert result.deltas == ()
    assert result.withheld_reason


def test_synthetic_vs_measured_quality_not_subtracted() -> None:
    a = make_trial("A")
    b = make_trial(
        "B",
        ventilation=Ventilation(Quantity(10, "cm/s"), FlowDirection.CONCURRENT),
        results=(
            Measurement(
                "flame_spread_rate",
                Quantity(1.5, "mm/s"),
                DataQuality.SYNTHETIC,
                TEST_PROV,
            ),
        ),
    )
    result = CompareTrials(_Repo([a, b])).execute(
        "A", "B", frozenset({Variable.FLOW_SPEED}), ["flame_spread_rate"]
    )
    assert result.compatibility.level is Comparability.DIRECT
    assert result.deltas == ()
    assert result.withheld_reason
    assert "SYNTHETIC" in result.withheld_reason


def test_delta_converts_mm_s_from_cm_s() -> None:
    a = make_trial("A")
    b = make_trial(
        "B",
        ventilation=Ventilation(Quantity(10, "cm/s"), FlowDirection.CONCURRENT),
        results=(
            Measurement(
                "flame_spread_rate",
                Quantity(0.15, "cm/s"),  # 1.5 mm/s
                DataQuality.MEASURED,
                TEST_PROV,
            ),
        ),
    )
    result = CompareTrials(_Repo([a, b])).execute(
        "A", "B", frozenset({Variable.FLOW_SPEED}), ["flame_spread_rate"]
    )
    assert result.compatibility.level is Comparability.DIRECT
    assert result.deltas[0].difference.unit == "mm/s"
    assert abs(result.deltas[0].difference.value - 0.5) < 1e-9


# ---- Curated BASS-II B16 / B19 (read-only of Yulian's data) ---------------------------------


def _curated_repo() -> JsonTrialRepository:
    return JsonTrialRepository([_CURATED])


def test_b16_condition_points_partial_descriptive_no_causal_deltas() -> None:
    """B16 Vg755 / Vg167 / Vg072: same sample, opposed, 18.2% O₂ — PARTIAL, no deltas."""
    compare = CompareTrials(_curated_repo())
    pairs = (
        ("BASS-II-B16-Vg755", "BASS-II-B16-Vg167"),
        ("BASS-II-B16-Vg167", "BASS-II-B16-Vg072"),
        ("BASS-II-B16-Vg755", "BASS-II-B16-Vg072"),
    )
    for left, right in pairs:
        result = compare.execute(
            left, right, frozenset({Variable.FLOW_SPEED}), ["flame_spread_rate"]
        )
        assert result.compatibility.level is Comparability.PARTIAL, left
        assert result.deltas == ()
        assert result.withheld_reason
        assert any("not independent replicates" in i.message for i in result.compatibility.issues)
        assert any(i.variable is Variable.PRESSURE for i in result.compatibility.issues)


def test_b16_table_s1_vf_unit_conversion_matches_published_x1000() -> None:
    """Vf_mm/s = (Vf x 10^3)_cm/s * 0.01 — verified against Link 2018 ESM Table S1."""
    repo = _curated_repo()
    expected = {
        "BASS-II-B16-Vg755": (6.78, 0.0678),
        "BASS-II-B16-Vg167": (7.62, 0.0762),
        "BASS-II-B16-Vg072": (5.68, 0.0568),
    }
    for trial_id, (vf_x1000, vf_mm_s) in expected.items():
        trial = repo.get(trial_id)
        assert trial is not None
        m = trial.measurement("flame_spread_rate")
        assert m is not None
        assert m.value.unit == "mm/s"
        assert abs(m.value.value - vf_mm_s) < 1e-9
        assert abs(vf_x1000 * 0.01 - vf_mm_s) < 1e-12


def test_b16_nonmonotonic_descriptive_ordering_of_recorded_vf() -> None:
    """Recorded Vf: Vg167 > Vg755 > Vg072 (Fig. 6a shape) — descriptive, not a causal Δ API."""
    repo = _curated_repo()
    rates = {}
    for tid in ("BASS-II-B16-Vg755", "BASS-II-B16-Vg167", "BASS-II-B16-Vg072"):
        m = repo.get(tid).measurement("flame_spread_rate")  # type: ignore[union-attr]
        assert m is not None
        rates[tid] = m.value.to("mm/s").value
    assert rates["BASS-II-B16-Vg167"] > rates["BASS-II-B16-Vg755"]
    assert rates["BASS-II-B16-Vg755"] > rates["BASS-II-B16-Vg072"]


def test_b16_vs_b19_oxygen_pair_partial_uncontrolled_pressure_and_sample() -> None:
    compare = CompareTrials(_curated_repo())
    result = compare.execute(
        "BASS-II-B16-Vg167",
        "BASS-II-B19-Vg167",
        frozenset({Variable.OXYGEN}),
        ["flame_spread_rate"],
    )
    assert result.compatibility.level is Comparability.PARTIAL
    assert result.deltas == ()
    assert result.withheld_reason
    # Different physical samples — no same-sample warning required; pressure still unknown.
    assert any(i.variable is Variable.PRESSURE for i in result.compatibility.issues)


def test_cylinder_vs_sheet_not_comparable() -> None:
    compare = CompareTrials(_curated_repo())
    result = compare.execute(
        "BASS-II-B16-Vg167",
        "BASS-II-FILM-100um-SR-extinction-context",
        frozenset({Variable.FLOW_SPEED}),
        ["flame_spread_rate"],
    )
    assert result.compatibility.level is Comparability.NOT_COMPARABLE
    assert result.deltas == ()


def test_assistant_still_groups_partial_pairs_without_equating_tiers() -> None:
    """Comparability.PARTIAL ≠ EvidenceTier.DIRECT; assistant may still form groups.

    `_comparable` only excludes NOT_COMPARABLE, so pressure-unknown B16 points remain
    groupable. EvidenceTier comes from EvidenceRank, not from Comparability.
    """
    from prometeo.application.use_cases.ask_research_assistant import comparable_groups
    from prometeo.domain.evidence.ranking import EvidenceTier, assess_trial, overall_tier
    from prometeo.domain.experiments.filters import TrialFilter

    repo = _curated_repo()
    trials = [
        repo.get("BASS-II-B16-Vg755"),
        repo.get("BASS-II-B16-Vg167"),
        repo.get("BASS-II-B16-Vg072"),
    ]
    assert all(t is not None for t in trials)
    typed = [t for t in trials if t is not None]

    groups = comparable_groups(typed)
    assert groups  # PARTIAL pairs still group (not NOT_COMPARABLE)

    compare = CompareTrials(repo)
    phys = compare.execute(
        "BASS-II-B16-Vg755",
        "BASS-II-B16-Vg167",
        frozenset({Variable.FLOW_SPEED}),
        ["flame_spread_rate"],
    )
    assert phys.compatibility.level is Comparability.PARTIAL
    assert phys.deltas == ()

    assessments = [
        assess_trial(t, TrialFilter(material="PMMA"), "flame_spread_rate") for t in typed
    ]
    # Evidence tier can be DIRECT while physical Comparability for the pair is PARTIAL.
    assert overall_tier(assessments) in {EvidenceTier.DIRECT, EvidenceTier.PARTIAL}
    assert phys.compatibility.level is not Comparability.DIRECT
