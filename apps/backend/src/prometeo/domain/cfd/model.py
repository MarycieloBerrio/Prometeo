"""CFD simulation records — numerical results, never experimental observations."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class CfdValidationStatus(StrEnum):
    PENDING_EXECUTION = "pending_execution"
    SOLVER_EXECUTED = "solver_executed"
    NUMERICALLY_CHECKED = "numerically_checked"
    # Never claim experimental model validation from non-reactive isothermal flow alone.


class ConvergenceStatus(StrEnum):
    CONVERGED = "converged"
    MAX_ITERATIONS_REACHED = "max_iterations_reached"
    SOLVER_FAILED = "solver_failed"
    NOT_RUN = "not_run"
    # Legacy value retained for reading older manifests during transition.
    NOT_CONVERGED_OR_NOT_RUN = "not_converged_or_not_run"


@dataclass(frozen=True, slots=True)
class CfdSimulation:
    simulation_id: str
    reference_trial_id: str
    solver: str
    solver_version: str
    model_type: str
    inlet_velocity_m_s: float
    inlet_velocity_cm_s: float
    oxygen_context_percent: float | None
    mesh_cell_count: int | None
    residuals: dict[str, float]
    mass_balance_error: float | None
    mass_balance_status: str
    mesh_independence: str
    convergence_status: ConvergenceStatus
    validation_status: CfdValidationStatus
    field_sample_path: str | None
    geometry_assumptions: tuple[str, ...]
    limitations: tuple[str, ...]
    result_kind: str = "numerical_simulation"
    solver_announced_convergence: bool = False
    convergence_evidence: str = ""
    mesh_quality_status: str = "not_verified"
    continuity_global_abs: float | None = None
