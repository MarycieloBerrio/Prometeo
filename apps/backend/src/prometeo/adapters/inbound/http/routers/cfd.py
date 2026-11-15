"""CFD Physics Lab HTTP routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from prometeo.adapters.inbound.http import dependencies as deps
from prometeo.adapters.inbound.http.schemas import (
    CfdFieldPointOut,
    CfdFieldSampleOut,
    CfdInterpretationOut,
    CfdSimulationOut,
    cfd_out,
)
from prometeo.application.use_cases.cfd_simulations import GetCfdSimulation, ListCfdSimulations
from prometeo.domain.shared.errors import NotFoundError

router = APIRouter(prefix="/api/v1/cfd", tags=["cfd"])


@router.get("/simulations", response_model=list[CfdSimulationOut])
def list_simulations(
    use_case: Annotated[ListCfdSimulations, Depends(deps.list_cfd)],
    trial_id: str | None = Query(default=None),
) -> list[CfdSimulationOut]:
    return [cfd_out(s) for s in use_case.execute(trial_id)]


@router.get("/simulations/{simulation_id}", response_model=CfdSimulationOut)
def get_simulation(
    simulation_id: str,
    use_case: Annotated[GetCfdSimulation, Depends(deps.get_cfd)],
) -> CfdSimulationOut:
    return cfd_out(use_case.execute(simulation_id))


@router.get("/simulations/{simulation_id}/field", response_model=CfdFieldSampleOut)
def get_field(
    simulation_id: str,
    use_case: Annotated[GetCfdSimulation, Depends(deps.get_cfd)],
) -> CfdFieldSampleOut:
    sample = use_case.field_sample(simulation_id)
    if sample is None:
        raise NotFoundError(f"No field sample for CFD simulation '{simulation_id}'")
    return CfdFieldSampleOut(
        simulation_id=sample.simulation_id,
        units=sample.units,
        downsample_stride=sample.downsample_stride,
        n_points_source=sample.n_points_source,
        points=[CfdFieldPointOut(**p) for p in sample.points],
    )


@router.get(
    "/simulations/{simulation_id}/interpretation",
    response_model=CfdInterpretationOut,
)
def interpretation(
    simulation_id: str,
    use_case: Annotated[GetCfdSimulation, Depends(deps.get_cfd)],
) -> CfdInterpretationOut:
    """Deterministic contextual explanation — not an LLM causal claim from CFD."""
    sim = use_case.execute(simulation_id)
    return CfdInterpretationOut(
        question="Why does measured flame spread peak at an intermediate opposed flow speed?",
        nasa_measured=[
            f"Linked experimental trial: {sim.reference_trial_id}.",
            "Opposed-flow flame spread rates for B16 come from Link et al. 2018 / Table S1 "
            "(curated measured Vf vs Vg).",
            "B16 oxygen context is 18.2% mole fraction as an experimental identifier.",
            "Absolute pressure for these rod rows remains undocumented in the curated set.",
        ],
        simulation_computed=[
            (
                "OpenFOAM isothermal laminar axial annular flow at "
                f"Vg = {sim.inlet_velocity_cm_s:g} cm/s."
            ),
            "Solved fields: velocity and relative kinematic pressure (incompressible).",
            "No temperature, O₂ species, pyrolysis, or flame-spread rate is computed.",
            f"Validation status: {sim.validation_status.value}; "
            f"convergence: {sim.convergence_status.value}.",
        ],
        literature_mechanisms=[
            "Link et al. 2018 attribute non-monotonic Vf(Vg) in microgravity to competing "
            "thermal-regime heat transfer and chemical-regime Damköhler effects.",
            "Forced ventilation changes boundary-layer thickness and oxygen supply to the flame.",
        ],
        cannot_conclude=[
            "This non-reactive CFD cannot by itself prove which mechanism caused the Vf peak.",
            "Do not treat the velocity field as a simulated flame or as predicted Vf.",
            "Isothermal forced flow cannot demonstrate 0g vs 1g buoyancy differences.",
            "Mesh independence is not demonstrated for the MVP annular wedge mesh.",
        ],
        sources=[
            "https://www.nature.com/articles/s41598-017-18398-4",
            "https://ntrs.nasa.gov/citations/20210011385",
            "data/simulations/cfd/manifests/" + sim.simulation_id + ".json",
        ],
    )
