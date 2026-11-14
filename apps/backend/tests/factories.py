"""Test-only builders. Values here are invented and never shipped as data."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from prometeo.domain.experiments.model import (
    DataQuality,
    FlowDirection,
    Fuel,
    Geometry,
    GeometryType,
    Investigation,
    Measurement,
    Phenomenon,
    Provenance,
    ThermalRegime,
    Trial,
    Ventilation,
)
from prometeo.domain.shared.quantity import Quantity

TEST_PROV = Provenance(reference="unit-test fixture", url="https://example.invalid/test")


def make_trial(trial_id: str = "T-1", **overrides: Any) -> Trial:
    base = Trial(
        id=trial_id,
        investigation=Investigation.BASS_II,
        sample_id=None,
        fuel=Fuel("test-material"),
        geometry=Geometry(GeometryType.SHEET, Quantity(0.25, "mm"), ThermalRegime.THIN),
        oxygen=Quantity(21, "%"),
        ventilation=Ventilation(Quantity(5, "cm/s"), FlowDirection.CONCURRENT),
        pressure=Quantity(101.3, "kPa"),
        phenomena=frozenset({Phenomenon.SPREAD}),
        provenance=TEST_PROV,
        results=(
            Measurement(
                "flame_spread_rate", Quantity(1.0, "mm/s"), DataQuality.MEASURED, TEST_PROV
            ),
        ),
    )
    return replace(base, **overrides)
