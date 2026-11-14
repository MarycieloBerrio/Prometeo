from dataclasses import replace

from prometeo.domain.experiments.model import FlowDirection, GeometryType, Ventilation
from prometeo.domain.physics.compatibility import Comparability, Variable, assess_compatibility
from prometeo.domain.shared.quantity import Quantity
from tests.factories import make_trial

VARY_FLOW = frozenset({Variable.FLOW_SPEED})


def test_only_varied_variable_differs_is_direct() -> None:
    a = make_trial("A")
    b = make_trial("B", ventilation=Ventilation(Quantity(10, "cm/s"), FlowDirection.CONCURRENT))
    assert assess_compatibility(a, b, VARY_FLOW).level is Comparability.DIRECT


def test_flow_direction_mismatch_blocks_comparison() -> None:
    a = make_trial("A")
    b = make_trial("B", ventilation=Ventilation(Quantity(10, "cm/s"), FlowDirection.OPPOSED))
    assert assess_compatibility(a, b, VARY_FLOW).level is Comparability.NOT_COMPARABLE


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
