from dataclasses import replace

from prometeo.domain.experiments.model import (
    FlowDirection,
    GeometryType,
    Investigation,
    ThermalRegime,
    Ventilation,
)
from prometeo.domain.physics.compatibility import (
    Comparability,
    Severity,
    Variable,
    assess_compatibility,
)
from prometeo.domain.shared.quantity import Quantity
from tests.factories import make_trial

VARY_FLOW = frozenset({Variable.FLOW_SPEED})
VARY_OXYGEN = frozenset({Variable.OXYGEN})
FAST = Ventilation(Quantity(10, "cm/s"), FlowDirection.CONCURRENT)


def test_only_varied_variable_differs_is_direct() -> None:
    """Full known controls + only flow_speed changed → DIRECT (not None-filled)."""
    a = make_trial("A")
    b = make_trial("B", ventilation=FAST)
    report = assess_compatibility(a, b, VARY_FLOW)
    assert report.level is Comparability.DIRECT
    assert a.pressure is not None and b.pressure is not None
    assert a.oxygen is not None and b.oxygen is not None


def test_flow_direction_mismatch_blocks_comparison() -> None:
    a = make_trial("A")
    b = make_trial("B", ventilation=Ventilation(Quantity(10, "cm/s"), FlowDirection.OPPOSED))
    assert assess_compatibility(a, b, VARY_FLOW).level is Comparability.NOT_COMPARABLE


def test_opposed_vs_concurrent_not_comparable_when_direction_controlled() -> None:
    a = make_trial("A", ventilation=Ventilation(Quantity(5, "cm/s"), FlowDirection.OPPOSED))
    b = make_trial("B", ventilation=Ventilation(Quantity(5, "cm/s"), FlowDirection.CONCURRENT))
    report = assess_compatibility(a, b, VARY_OXYGEN)
    assert report.level is Comparability.NOT_COMPARABLE
    assert any(
        i.variable is Variable.FLOW_DIRECTION and i.severity is Severity.BLOCKING
        for i in report.issues
    )


def test_quiescent_vs_opposed_not_comparable() -> None:
    a = make_trial("A", ventilation=Ventilation(Quantity(0, "cm/s"), FlowDirection.QUIESCENT))
    b = make_trial("B", ventilation=Ventilation(Quantity(5, "cm/s"), FlowDirection.OPPOSED))
    report = assess_compatibility(a, b, VARY_FLOW)
    assert report.level is Comparability.NOT_COMPARABLE


def test_geometry_mismatch_blocks_comparison() -> None:
    a = make_trial("A")
    b = make_trial("B", geometry=replace(a.geometry, type=GeometryType.CYLINDER))
    report = assess_compatibility(a, b, VARY_FLOW)
    assert report.level is Comparability.NOT_COMPARABLE
    assert any(i.variable is Variable.GEOMETRY for i in report.issues)


def test_oxygen_difference_is_partial() -> None:
    a = make_trial("A")
    b = make_trial("B", oxygen=Quantity(30, "%"))
    assert assess_compatibility(a, b, VARY_FLOW).level is Comparability.PARTIAL


def test_both_pressures_unknown_never_direct() -> None:
    """Bug fix: None/None must not silently count as a controlled match."""
    a = make_trial("A", pressure=None)
    b = make_trial("B", pressure=None, ventilation=FAST)
    report = assess_compatibility(a, b, VARY_FLOW)
    assert report.level is Comparability.PARTIAL
    pressure_issues = [i for i in report.issues if i.variable is Variable.PRESSURE]
    assert pressure_issues
    assert all(i.severity is Severity.WARNING for i in pressure_issues)


def test_both_oxygen_unknown_is_partial_not_causal_ready() -> None:
    a = make_trial("A", oxygen=None)
    b = make_trial("B", oxygen=None, ventilation=FAST)
    report = assess_compatibility(a, b, VARY_FLOW)
    assert report.level is Comparability.PARTIAL
    assert any(
        i.variable is Variable.OXYGEN and i.severity is Severity.WARNING
        for i in report.issues
    )


def test_unknown_thermal_regime_warns() -> None:
    geom = replace(make_trial().geometry, thermal_regime=ThermalRegime.UNKNOWN)
    a = make_trial("A", geometry=geom)
    b = make_trial("B", ventilation=FAST)
    report = assess_compatibility(a, b, VARY_FLOW)
    assert report.level is Comparability.PARTIAL
    assert any(i.variable is Variable.THERMAL_REGIME for i in report.issues)


def test_unknown_flow_direction_warns() -> None:
    a = make_trial("A", ventilation=Ventilation(Quantity(5, "cm/s"), FlowDirection.UNKNOWN))
    b = make_trial("B", ventilation=Ventilation(Quantity(10, "cm/s"), FlowDirection.UNKNOWN))
    report = assess_compatibility(a, b, VARY_FLOW)
    assert report.level is Comparability.PARTIAL


def test_synthetic_vs_real_blocked() -> None:
    a = make_trial("A")
    b = make_trial("B", investigation=Investigation.SYNTHETIC)
    report = assess_compatibility(a, b, VARY_FLOW)
    assert report.level is Comparability.NOT_COMPARABLE


def test_oxygen_percent_and_fraction_within_tol_match() -> None:
    a = make_trial("A", oxygen=Quantity(21, "%"))
    b = make_trial("B", oxygen=Quantity(0.21, "fraction"), ventilation=FAST)
    report = assess_compatibility(a, b, VARY_FLOW)
    assert report.level is Comparability.DIRECT


def test_flow_speed_cm_s_and_m_s_within_tol_match_when_oxygen_varied() -> None:
    a = make_trial("A", ventilation=Ventilation(Quantity(5, "cm/s"), FlowDirection.CONCURRENT))
    b = make_trial(
        "B",
        oxygen=Quantity(25, "%"),
        ventilation=Ventilation(Quantity(0.05, "m/s"), FlowDirection.CONCURRENT),
    )
    report = assess_compatibility(a, b, VARY_OXYGEN)
    assert report.level is Comparability.DIRECT


def test_isolation_invalid_when_oxygen_also_changes() -> None:
    a = make_trial("A")
    b = make_trial("B", oxygen=Quantity(30, "%"), ventilation=FAST)
    report = assess_compatibility(a, b, VARY_FLOW)
    assert report.level is Comparability.PARTIAL
    assert any("Invalid single-factor isolation" in i.message for i in report.issues)


def test_rel_tol_is_heuristic_near_zero_documented_via_close_match() -> None:
    """Near-zero values use max(|a|,|b|) as scale in Quantity.is_close — not absolute ε."""
    zero = Ventilation(Quantity(0.0, "cm/s"), FlowDirection.CONCURRENT)
    a = make_trial("A", ventilation=zero)
    b = make_trial("B", oxygen=Quantity(25, "%"), ventilation=zero)
    assert assess_compatibility(a, b, VARY_OXYGEN).level is Comparability.DIRECT


def test_geometry_mismatch_not_waived_by_listing_geometry_in_varied() -> None:
    a = make_trial("A")
    b = make_trial("B", geometry=replace(a.geometry, type=GeometryType.CYLINDER))
    report = assess_compatibility(
        a, b, frozenset({Variable.FLOW_SPEED, Variable.GEOMETRY})
    )
    assert report.level is Comparability.NOT_COMPARABLE
    assert any("cannot be waived" in i.message for i in report.issues)


def test_same_sample_condition_points_are_partial_not_replicates() -> None:
    a = make_trial("A", sample_id="B16")
    b = make_trial("B", sample_id="B16", ventilation=FAST)
    report = assess_compatibility(a, b, VARY_FLOW)
    assert report.level is Comparability.PARTIAL
    assert any("not independent replicates" in i.message for i in report.issues)


def test_simultaneous_oxygen_and_flow_drift_is_partial() -> None:
    a = make_trial("A")
    b = make_trial("B", oxygen=Quantity(30, "%"), ventilation=FAST)
    # Only flow marked varied — oxygen also changed → isolation invalid / PARTIAL
    report = assess_compatibility(a, b, VARY_FLOW)
    assert report.level is Comparability.PARTIAL
    assert any(i.variable is Variable.OXYGEN for i in report.issues)


def test_oxygen_18p2_vs_17p5_not_matched_by_relative_five_percent() -> None:
    """B16/B19 O2 gap is ~3.85% relative but 0.7 pp absolute — not a controlled match."""
    a = make_trial("A", oxygen=Quantity(18.2, "%"))
    b = make_trial("B", oxygen=Quantity(17.5, "%"), ventilation=FAST)
    report = assess_compatibility(a, b, VARY_FLOW)
    assert report.level is Comparability.PARTIAL
    assert any(
        i.variable is Variable.OXYGEN
        and "percentage points" in i.message
        and i.severity is Severity.WARNING
        for i in report.issues
    )


def test_oxygen_within_published_band_counts_as_controlled_match() -> None:
    a = make_trial("A", oxygen=Quantity(18.2, "%"))
    b = make_trial("B", oxygen=Quantity(18.4, "%"), ventilation=FAST)
    report = assess_compatibility(a, b, VARY_FLOW)
    ox_warn = [
        i for i in report.issues
        if i.variable is Variable.OXYGEN and i.severity is Severity.WARNING
    ]
    assert not ox_warn
    assert report.level is Comparability.DIRECT


def test_flow_direction_mismatch_not_waived_by_varied() -> None:
    a = make_trial("A", ventilation=Ventilation(Quantity(5, "cm/s"), FlowDirection.OPPOSED))
    b = make_trial("B", ventilation=Ventilation(Quantity(5, "cm/s"), FlowDirection.CONCURRENT))
    report = assess_compatibility(a, b, frozenset({Variable.FLOW_DIRECTION}))
    assert report.level is Comparability.NOT_COMPARABLE
    assert any("cannot be waived" in i.message for i in report.issues)


def test_fuel_mismatch_not_waived_by_varied() -> None:
    from prometeo.domain.experiments.model import Fuel

    a = make_trial("A")
    b = make_trial("B", fuel=Fuel("other-material"), ventilation=FAST)
    report = assess_compatibility(a, b, frozenset({Variable.FUEL, Variable.FLOW_SPEED}))
    assert report.level is Comparability.NOT_COMPARABLE


def test_varied_flow_speed_without_real_change_is_partial() -> None:
    a = make_trial("A")
    b = make_trial("B")  # same 5 cm/s
    report = assess_compatibility(a, b, VARY_FLOW)
    assert report.level is Comparability.PARTIAL
    assert any("no experimental change established" in i.message for i in report.issues)


def test_multi_factor_oxygen_and_flow_both_varied_is_partial() -> None:
    a = make_trial("A")
    b = make_trial("B", oxygen=Quantity(30, "%"), ventilation=FAST)
    report = assess_compatibility(a, b, frozenset({Variable.OXYGEN, Variable.FLOW_SPEED}))
    assert report.level is Comparability.PARTIAL
    assert any("Multiple experimental factors" in i.message for i in report.issues)
