from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from prometeo.adapters.inbound.http import dependencies as deps
from prometeo.adapters.inbound.http.schemas import TrialOut, trial_out
from prometeo.application.use_cases.explore_experiments import ExploreExperiments
from prometeo.domain.experiments.filters import TrialFilter
from prometeo.domain.experiments.model import (
    FlowDirection,
    GeometryType,
    Investigation,
    Phenomenon,
)
from prometeo.domain.shared.quantity import Quantity

router = APIRouter(prefix="/api/v1/trials", tags=["experiments"])


@router.get("", response_model=list[TrialOut])
def list_trials(
    use_case: Annotated[ExploreExperiments, Depends(deps.explore)],
    include_synthetic: Annotated[bool, Depends(deps.include_synthetic)],
    investigation: Investigation | None = None,
    material: str | None = None,
    geometry: GeometryType | None = None,
    phenomenon: Phenomenon | None = None,
    flow_direction: FlowDirection | None = None,
    oxygen_min: Annotated[float | None, Query(description="O2 volume fraction 0..1")] = None,
    oxygen_max: Annotated[float | None, Query(description="O2 volume fraction 0..1")] = None,
    flow_min_cm_s: float | None = None,
    flow_max_cm_s: float | None = None,
) -> list[TrialOut]:
    criteria = TrialFilter(
        investigation=investigation,
        material=material,
        geometry=geometry,
        phenomenon=phenomenon,
        flow_direction=flow_direction,
        oxygen_min=_q(oxygen_min, "fraction"),
        oxygen_max=_q(oxygen_max, "fraction"),
        flow_min=_q(flow_min_cm_s, "cm/s"),
        flow_max=_q(flow_max_cm_s, "cm/s"),
        include_synthetic=include_synthetic,
    )
    return [trial_out(t) for t in use_case.search(criteria)]


@router.get("/{trial_id}", response_model=TrialOut)
def get_trial(
    trial_id: str, use_case: Annotated[ExploreExperiments, Depends(deps.explore)]
) -> TrialOut:
    return trial_out(use_case.get(trial_id))


def _q(value: float | None, unit: str) -> Quantity | None:
    return None if value is None else Quantity(value, unit)
