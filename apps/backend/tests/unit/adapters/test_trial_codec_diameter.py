"""Explicit rod diameter (geometry.diameter) is read without changing legacy `thickness`."""

from __future__ import annotations

from prometeo.adapters.outbound.persistence.trial_codec import trial_from_json
from prometeo.domain.physics.compatibility import Variable, assess_compatibility
from prometeo.domain.shared.quantity import Quantity

_BASE = {
    "id": "T-ROD",
    "investigation": "BASS-II",
    "sample_id": "B16",
    "fuel": {"material": "PMMA"},
    "ventilation": {"speed": {"value": 1.0, "unit": "cm/s"}, "direction": "opposed"},
    "oxygen": {"value": 18.2, "unit": "%"},
    "phenomena": ["spread"],
    "provenance": {"reference": "test"},
}


def _rod(trial_id: str, diameter: bool) -> dict[str, object]:
    geometry: dict[str, object] = {
        "type": "cylinder",
        "thickness": {"value": 6.4, "unit": "mm"},
        "thermal_regime": "thick",
    }
    if diameter:
        geometry["diameter"] = {"value": 6.4, "unit": "mm"}
    return {**_BASE, "id": trial_id, "geometry": geometry}


def test_diameter_is_parsed_and_thickness_is_unchanged() -> None:
    trial = trial_from_json(_rod("A", diameter=True))
    assert trial.geometry.diameter == Quantity(6.4, "mm")
    assert trial.geometry.thickness == Quantity(6.4, "mm")


def test_legacy_record_without_diameter_still_loads() -> None:
    trial = trial_from_json(_rod("A", diameter=False))
    assert trial.geometry.diameter is None


def test_validator_names_the_explicit_diameter_when_present() -> None:
    a, b = trial_from_json(_rod("A", True)), trial_from_json(_rod("B", True))
    report = assess_compatibility(a, b, frozenset({Variable.FLOW_SPEED}))
    info = [i for i in report.issues if i.variable is Variable.THICKNESS]
    assert any("geometry.diameter" in i.message for i in info)
