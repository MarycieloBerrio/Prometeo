"""Experiment Explorer filtering rules (pure)."""

from __future__ import annotations

from dataclasses import dataclass

from prometeo.domain.experiments.model import (
    FlowDirection,
    GeometryType,
    Investigation,
    Phenomenon,
    Trial,
)
from prometeo.domain.shared.quantity import Quantity


@dataclass(frozen=True, slots=True)
class TrialFilter:
    investigation: Investigation | None = None
    material: str | None = None
    geometry: GeometryType | None = None
    phenomenon: Phenomenon | None = None
    flow_direction: FlowDirection | None = None
    oxygen_min: Quantity | None = None
    oxygen_max: Quantity | None = None
    flow_min: Quantity | None = None
    flow_max: Quantity | None = None
    include_synthetic: bool = False

    def matches(self, trial: Trial) -> bool:
        if trial.is_synthetic and not self.include_synthetic:
            return False
        if self.investigation and trial.investigation is not self.investigation:
            return False
        if self.material and self.material.lower() not in trial.fuel.material.lower():
            return False
        if self.geometry and trial.geometry.type is not self.geometry:
            return False
        if self.phenomenon and self.phenomenon not in trial.phenomena:
            return False
        if self.flow_direction and trial.ventilation.direction is not self.flow_direction:
            return False
        if not _in_range(trial.oxygen, self.oxygen_min, self.oxygen_max):
            return False
        return _in_range(trial.ventilation.speed, self.flow_min, self.flow_max)


def _in_range(value: Quantity | None, lo: Quantity | None, hi: Quantity | None) -> bool:
    if lo is None and hi is None:
        return True
    if value is None:
        return False  # unknown condition never silently satisfies a numeric filter
    v = value.canonical()
    if lo is not None and v < lo.canonical():
        return False
    return not (hi is not None and v > hi.canonical())
