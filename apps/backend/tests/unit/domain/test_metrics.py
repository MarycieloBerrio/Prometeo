import math

import pytest

from prometeo.domain.physics.metrics import (
    flame_spread_velocity,
    flame_spread_velocity_fit,
    heat_release_rate_from_o2,
    peclet_number,
)
from prometeo.domain.shared.errors import InvalidMeasurementError
from prometeo.domain.shared.quantity import Quantity as Q


def test_spread_velocity_two_points_in_mm_per_s() -> None:
    v = flame_spread_velocity(Q(10, "mm"), Q(0, "s"), Q(3, "cm"), Q(10, "s"))
    assert v.unit == "mm/s"
    assert v.value == pytest.approx(2.0)


def test_spread_velocity_requires_increasing_time() -> None:
    with pytest.raises(InvalidMeasurementError):
        flame_spread_velocity(Q(0, "mm"), Q(5, "s"), Q(1, "mm"), Q(5, "s"))


def test_spread_velocity_rejects_negative() -> None:
    with pytest.raises(InvalidMeasurementError, match="negative"):
        flame_spread_velocity(Q(10, "mm"), Q(0, "s"), Q(0, "mm"), Q(10, "s"))


def test_spread_velocity_caller_must_orient_decreasing_lab_axis() -> None:
    """Front advancing in -x lab frame: flip axis before calling; do not abs() silently."""
    with pytest.raises(InvalidMeasurementError, match="negative"):
        flame_spread_velocity(Q(20, "mm"), Q(0, "s"), Q(10, "mm"), Q(5, "s"))
    # Oriented axis x' = x0 - x recovers the physical advance rate.
    v = flame_spread_velocity(Q(0, "mm"), Q(0, "s"), Q(10, "mm"), Q(5, "s"))
    assert v.value == pytest.approx(2.0)


def test_spread_velocity_rejects_non_finite() -> None:
    with pytest.raises(InvalidMeasurementError, match="finite"):
        flame_spread_velocity(Q(math.nan, "mm"), Q(0, "s"), Q(1, "mm"), Q(1, "s"))


def test_spread_velocity_fit_recovers_slope() -> None:
    xs = [Q(1.5 * t, "mm") for t in range(6)]
    ts = [Q(t, "s") for t in range(6)]
    assert flame_spread_velocity_fit(xs, ts).value == pytest.approx(1.5)


def test_spread_velocity_fit_rejects_duplicate_times() -> None:
    xs = [Q(0, "mm"), Q(1, "mm"), Q(2, "mm")]
    ts = [Q(0, "s"), Q(1, "s"), Q(1, "s")]
    with pytest.raises(InvalidMeasurementError, match="Duplicate"):
        flame_spread_velocity_fit(xs, ts)


def test_spread_velocity_fit_rejects_negative_slope() -> None:
    xs = [Q(5, "mm"), Q(3, "mm"), Q(1, "mm")]
    ts = [Q(0, "s"), Q(1, "s"), Q(2, "s")]
    with pytest.raises(InvalidMeasurementError, match="negative"):
        flame_spread_velocity_fit(xs, ts)


def test_spread_velocity_fit_unit_mismatch() -> None:
    with pytest.raises(InvalidMeasurementError):
        flame_spread_velocity_fit([Q(1, "mm"), Q(2, "mm")], [Q(0, "mm"), Q(1, "s")])


def test_heat_release_rate_oxygen_consumption() -> None:
    # 13.1 kJ/g * 1 g / 10 s = 1.31 kW
    assert heat_release_rate_from_o2(Q(1, "g"), Q(10, "s")).value == pytest.approx(1.31)


def test_heat_release_rejects_wrong_dimension() -> None:
    with pytest.raises(InvalidMeasurementError):
        heat_release_rate_from_o2(Q(1, "mm"), Q(10, "s"))


def test_heat_release_rejects_zero_interval() -> None:
    with pytest.raises(InvalidMeasurementError):
        heat_release_rate_from_o2(Q(1, "g"), Q(0, "s"))


def test_peclet_number() -> None:
    pe = peclet_number(Q(5, "cm/s"), Q(1, "cm"), Q(0.2, "cm^2/s"))
    assert pe == pytest.approx(25.0)


def test_peclet_rejects_non_finite_velocity() -> None:
    with pytest.raises(InvalidMeasurementError, match="finite"):
        peclet_number(Q(math.inf, "cm/s"), Q(1, "cm"), Q(0.2, "cm^2/s"))
