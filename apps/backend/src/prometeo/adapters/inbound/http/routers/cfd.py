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
    points_out: list[CfdFieldPointOut] = []
    for p in sample.points:
        points_out.append(
            CfdFieldPointOut(
                x=float(p["x"]),
                y=float(p["y"]),
                z=float(p["z"]),
                u_mag=float(p["u_mag"]),
                p=float(p["p"]),
                ux=float(p["ux"]) if "ux" in p else None,
                uy=float(p["uy"]) if "uy" in p else None,
                uz=float(p["uz"]) if "uz" in p else None,
            )
        )
    return CfdFieldSampleOut(
        simulation_id=sample.simulation_id,
        units=sample.units,
        downsample_stride=sample.downsample_stride,
        n_points_source=sample.n_points_source,
        points=points_out,
        viewer_note=sample.viewer_note,
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
        question=(
            "Why does measured flame spread appear to peak at an intermediate opposed-flow speed?"
        ),
        nasa_measured=[
            f"Linked experimental condition point: {sim.reference_trial_id}.",
            "B16 Vf values come from Link et al. 2018, Supplementary Table S1, which tabulates "
            "10³·Vf in cm/s (e.g. 5.68 → Vf = 5.68×10⁻³ cm/s = 0.0568 mm/s).",  # noqa: RUF001
            "The B16 points are condition points on ONE rod: the opposed flow was stepped down "
            "from 7.55 to 0.72 cm/s during a single burn (≥ 1 min per step, Link et al. 2018). "
            "They are not independent ignitions; no replicates or uncertainty bars exist.",
            "Within that sequence Vf is non-monotonic in Vg: an apparent maximum at an "
            "intermediate speed, observed once — not a statistically demonstrated peak.",
            "B16 oxygen context is 18.2% (volume fraction), an experimental identifier.",
            "Absolute pressure for these rod rows remains undocumented in the curated set.",
        ],
        simulation_computed=[
            (
                "OpenFOAM isothermal laminar axial annular flow at "
                f"Vg = {sim.inlet_velocity_cm_s:g} cm/s."
            ),
            "Solved fields: velocity and relative kinematic pressure (incompressible).",
            "No temperature, O₂ species, pyrolysis, radiation or flame-spread rate is computed.",
            f"Validation status: {sim.validation_status.value}; "
            f"convergence: {sim.convergence_status.value}.",
            (
                sim.convergence_evidence
                or "Convergence evidence not recorded in the CFD manifesto."
            ),
        ],
        literature_mechanisms=[
            "Link et al. 2018 (Discussion) describe a thermal regime: at low opposed flow, a "
            "faster flow moves the flame closer to the surface, raises heat transfer to the "
            "solid ahead and increases Vf.",
            "They describe a chemical regime: at larger flow (or lower O₂), the flow cools the "
            "gas-phase reaction, the flame weakens and spread slows, eventually to blow-off. They "
            "characterise it with a convective Damköhler number written Da = t_chem / t_flow "
            "(their Eq. 1). Quoted only: Prometeo does not evaluate Da or its trend with Vg.",
            "At very low flow they attribute slow spread and extinction (no spread below "
            "~0.6 cm/s) to surface radiative losses and slow oxygen transport, and state that "
            "better diagnostics are needed to separate the two. Blow-off at high flow was not "
            "observed in the ISS tests.",
        ],
        cannot_conclude=[
            "This non-reactive, isothermal CFD has no combustion, radiation or species: it "
            "cannot demonstrate either regime or which one produced the apparent maximum.",
            "The apparent maximum rests on single values from one sample burned in one "
            "sequence, so Vg is confounded with time and position along the rod; causality "
            "of Vg alone is not demonstrated.",
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
