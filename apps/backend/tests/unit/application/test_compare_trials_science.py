"""Scientific rules for CompareTrials: withhold causal deltas unless DIRECT."""

from __future__ import annotations

from dataclasses import replace

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
