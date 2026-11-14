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
