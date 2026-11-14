"""Deterministic scientific metrics.

Every function validates its physical assumptions and raises `InvalidMeasurementError`
instead of returning a plausible-looking number. LLMs never compute these values.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from prometeo.domain.shared.errors import InvalidMeasurementError
from prometeo.domain.shared.quantity import Dimension, Quantity

# Oxygen-consumption calorimetry constant used in the NASA BASS-II summary report.
# Valid only when O2 consumption is measured and the procedure's assumptions hold.
# See NASA/TM-20210011385 (Olson et al.): ~13.1 kJ heat released per gram O₂ consumed.
HEAT_OF_COMBUSTION_PER_O2_KJ_PER_G = 13.1


def _require(q: Quantity, dim: Dimension, label: str) -> float:
    if q.dimension is not dim:
        raise InvalidMeasurementError(f"{label} must be a {dim}, got unit '{q.unit}'")
    value = q.canonical()
    if not math.isfinite(value):
        raise InvalidMeasurementError(f"{label} must be finite, got {q}")
    return value


def flame_spread_velocity(
    x1: Quantity, t1: Quantity, x2: Quantity, t2: Quantity
) -> Quantity:
    """v_f = (x_f(t2) - x_f(t1)) / (t2 - t1), returned in mm/s.

    Caller is responsible for ensuring both positions track the SAME physical front.
    Negative results are rejected: a signed retreat is not reported as spread rate here.
    """
    p1 = _require(x1, Dimension.LENGTH, "x1")
    p2 = _require(x2, Dimension.LENGTH, "x2")
    s1 = _require(t1, Dimension.TIME, "t1")
    s2 = _require(t2, Dimension.TIME, "t2")
    if s2 <= s1:
        raise InvalidMeasurementError("t2 must be strictly greater than t1")
    slope = (p2 - p1) / (s2 - s1)
    if slope < 0:
        raise InvalidMeasurementError(
            "Flame spread velocity is negative; check front identity and coordinate sense"
        )
    return Quantity(slope, "m/s").to("mm/s")


def flame_spread_velocity_fit(
    positions: Sequence[Quantity], times: Sequence[Quantity]
) -> Quantity:
    """Least-squares slope of front position vs time (more robust than two points), in mm/s."""
    if len(positions) != len(times) or len(positions) < 2:
        raise InvalidMeasurementError("Need at least two (position, time) pairs of equal length")
    xs = [_require(p, Dimension.LENGTH, "position") for p in positions]
    ts = [_require(t, Dimension.TIME, "time") for t in times]
    if len(ts) != len(set(ts)):
        raise InvalidMeasurementError("Duplicate timestamps are not allowed")
    # Sort by time so callers may pass unordered samples; duplicates already rejected.
    ordered = sorted(zip(ts, xs, strict=True), key=lambda pair: pair[0])
    ts = [t for t, _ in ordered]
    xs = [x for _, x in ordered]
    n = len(ts)
    t_mean, x_mean = sum(ts) / n, sum(xs) / n
    denom = sum((t - t_mean) ** 2 for t in ts)
    if denom == 0:
        raise InvalidMeasurementError("All timestamps are identical")
    slope = sum((t - t_mean) * (x - x_mean) for t, x in zip(ts, xs, strict=True)) / denom
    if not math.isfinite(slope):
        raise InvalidMeasurementError("Fitted flame spread velocity is not finite")
    if slope < 0:
        raise InvalidMeasurementError(
            "Fitted flame spread velocity is negative; check front identity and coordinate sense"
        )
    return Quantity(slope, "m/s").to("mm/s")


def heat_release_rate_from_o2(delta_mass_o2: Quantity, delta_t: Quantity) -> Quantity:
    """Q ≈ 13.1 kJ/g_O2 · Δm_O2 / Δt, in kW (oxygen-consumption approximation)."""
    dm = _require(delta_mass_o2, Dimension.MASS, "delta_mass_o2")  # g
    dt = _require(delta_t, Dimension.TIME, "delta_t")  # s
    if dm < 0:
        raise InvalidMeasurementError("Consumed O2 mass cannot be negative")
    if dt <= 0:
        raise InvalidMeasurementError("delta_t must be positive")
    return Quantity(HEAT_OF_COMBUSTION_PER_O2_KJ_PER_G * dm / dt, "kW")


def peclet_number(velocity: Quantity, length: Quantity, diffusivity: Quantity) -> float:
    """Pe = U·L / D — ratio of convective to diffusive transport.

    Only meaningful when U, L and D are defined at consistent scales for the same trial.
    """
    u = _require(velocity, Dimension.VELOCITY, "velocity")
    length_m = _require(length, Dimension.LENGTH, "length")
    d = _require(diffusivity, Dimension.DIFFUSIVITY, "diffusivity")
    if d <= 0 or length_m <= 0:
        raise InvalidMeasurementError("length and diffusivity must be positive")
    pe = abs(u) * length_m / d
    if not math.isfinite(pe):
        raise InvalidMeasurementError("Péclet number is not finite")
    return pe
