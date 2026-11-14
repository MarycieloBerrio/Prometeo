"""Physical quantities with explicit units.

Every number that enters the domain carries its unit. Conversions are limited to the
dimensions Prometeo actually compares; unknown units raise instead of guessing.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from prometeo.domain.shared.errors import UnitError


class Dimension(StrEnum):
    LENGTH = "length"
    TIME = "time"
    VELOCITY = "velocity"
    PRESSURE = "pressure"
    FRACTION = "fraction"  # O2 concentration as volume/mole fraction (0..1)
    POWER = "power"
    MASS = "mass"
    DIFFUSIVITY = "diffusivity"
    DIMENSIONLESS = "dimensionless"


# unit -> (dimension, factor to SI-ish canonical unit)
_UNITS: dict[str, tuple[Dimension, float]] = {
    # length -> m
    "m": (Dimension.LENGTH, 1.0),
    "cm": (Dimension.LENGTH, 1e-2),
    "mm": (Dimension.LENGTH, 1e-3),
    "um": (Dimension.LENGTH, 1e-6),
    # time -> s
    "s": (Dimension.TIME, 1.0),
    "ms": (Dimension.TIME, 1e-3),
    "min": (Dimension.TIME, 60.0),
    # velocity -> m/s
    "m/s": (Dimension.VELOCITY, 1.0),
    "cm/s": (Dimension.VELOCITY, 1e-2),
    "mm/s": (Dimension.VELOCITY, 1e-3),
    # pressure -> kPa
    "kPa": (Dimension.PRESSURE, 1.0),
    "Pa": (Dimension.PRESSURE, 1e-3),
    "atm": (Dimension.PRESSURE, 101.325),
    "psia": (Dimension.PRESSURE, 6.894757),
    # fraction -> 0..1
    "fraction": (Dimension.FRACTION, 1.0),
    "%": (Dimension.FRACTION, 1e-2),
    # power -> kW
    "kW": (Dimension.POWER, 1.0),
    "W": (Dimension.POWER, 1e-3),
    # mass -> g
    "g": (Dimension.MASS, 1.0),
    "mg": (Dimension.MASS, 1e-3),
    "kg": (Dimension.MASS, 1e3),
    # diffusivity -> m^2/s
    "m^2/s": (Dimension.DIFFUSIVITY, 1.0),
    "cm^2/s": (Dimension.DIFFUSIVITY, 1e-4),
    # dimensionless
    "1": (Dimension.DIMENSIONLESS, 1.0),
}


def dimension_of(unit: str) -> Dimension:
    try:
        return _UNITS[unit][0]
    except KeyError as exc:
        raise UnitError(f"Unknown unit '{unit}'") from exc


@dataclass(frozen=True, slots=True)
class Quantity:
    value: float
    unit: str

    def __post_init__(self) -> None:
        dimension_of(self.unit)  # validate eagerly

    @property
    def dimension(self) -> Dimension:
        return dimension_of(self.unit)

    def to(self, unit: str) -> Quantity:
        src_dim, src_factor = _UNITS[self.unit]
        dst_dim = dimension_of(unit)
        if src_dim is not dst_dim:
            raise UnitError(f"Cannot convert {self.unit} ({src_dim}) to {unit} ({dst_dim})")
        dst_factor = _UNITS[unit][1]
        return Quantity(self.value * src_factor / dst_factor, unit)

    def canonical(self) -> float:
        """Value expressed in the canonical unit of its dimension."""
        return self.value * _UNITS[self.unit][1]

    def is_close(self, other: Quantity, rel_tol: float) -> bool:
        if self.dimension is not other.dimension:
            return False
        a, b = self.canonical(), other.canonical()
        scale = max(abs(a), abs(b))
        return scale == 0 or abs(a - b) <= rel_tol * scale

    def __str__(self) -> str:
        return f"{self.value:g} {self.unit}"
