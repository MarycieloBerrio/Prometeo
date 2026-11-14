"""Unified experimental record — one standard structure for every trial, whatever its program.

BASS-II, FLEX and SAFFIRE are NOT a homogeneous statistical population. The catalog can hold
them together, but comparability is decided by `prometeo.domain.physics.compatibility`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from prometeo.domain.shared.quantity import Quantity


class Investigation(StrEnum):
    BASS_II = "BASS-II"
    FLEX = "FLEX"
    SAFFIRE_I = "SAFFIRE-I"
    FLAME_SPREAD_MODELING = "FLAME-SPREAD-MODELING"
    SYNTHETIC = "SYNTHETIC"  # test/dev fixtures only — never presented as NASA data


class GeometryType(StrEnum):
    SHEET = "sheet"
    CYLINDER = "cylinder"
    SPHERE = "sphere"
    DROPLET = "droplet"
    OTHER = "other"


class ThermalRegime(StrEnum):
    """Thermally thin vs thick solids cannot be compared without accounting for geometry."""

    THIN = "thin"
    THICK = "thick"
    UNKNOWN = "unknown"


class FlowDirection(StrEnum):
    CONCURRENT = "concurrent"
    OPPOSED = "opposed"
    QUIESCENT = "quiescent"
    UNKNOWN = "unknown"


class Phenomenon(StrEnum):
    IGNITION = "ignition"
    SPREAD = "spread"
    EXTINCTION = "extinction"


class DataQuality(StrEnum):
    """How much certainty a value deserves. Ordered from strongest to weakest."""

    MEASURED = "measured"  # reported measurement, reviewed against the source
    DERIVED = "derived"  # computed by Prometeo from measured data (method recorded)
    EXTRACTED = "extracted"  # pulled automatically from a document, not yet reviewed
    UNAVAILABLE = "unavailable"
    SYNTHETIC = "synthetic"  # fabricated fixture for development; never evidence


@dataclass(frozen=True, slots=True)
class Provenance:
    reference: str  # human-readable citation
    source_file: str | None = None
    doi: str | None = None
    url: str | None = None
    page: str | None = None
    version: str | None = None

    @property
    def is_traceable(self) -> bool:
        return bool(self.doi or self.url or self.source_file)


@dataclass(frozen=True, slots=True)
class Fuel:
    material: str
    composition: str | None = None


@dataclass(frozen=True, slots=True)
class Geometry:
    type: GeometryType
    thickness: Quantity | None = None
    thermal_regime: ThermalRegime = ThermalRegime.UNKNOWN


@dataclass(frozen=True, slots=True)
class Ventilation:
    speed: Quantity | None
    direction: FlowDirection = FlowDirection.UNKNOWN


@dataclass(frozen=True, slots=True)
class Measurement:
    name: str  # e.g. "flame_spread_rate", "heat_release_rate"
    value: Quantity
    quality: DataQuality
    provenance: Provenance
    uncertainty: Quantity | None = None
    method: str | None = None  # required when quality == DERIVED


@dataclass(frozen=True, slots=True)
class MediaRef:
    kind: str  # "video" | "image"
    uri: str
    start_s: float | None = None
    end_s: float | None = None
    provenance: Provenance | None = None


@dataclass(frozen=True, slots=True)
class Trial:
    id: str
    investigation: Investigation
    sample_id: str | None
    fuel: Fuel
    geometry: Geometry
    oxygen: Quantity | None  # O2 concentration (fraction or %)
    ventilation: Ventilation
    pressure: Quantity | None
    phenomena: frozenset[Phenomenon]
    provenance: Provenance
    results: tuple[Measurement, ...] = ()
    media: tuple[MediaRef, ...] = ()
    notes: str | None = None
    tags: frozenset[str] = field(default_factory=frozenset)

    def measurement(self, name: str) -> Measurement | None:
        return next((m for m in self.results if m.name == name), None)

    @property
    def is_synthetic(self) -> bool:
        return self.investigation is Investigation.SYNTHETIC
