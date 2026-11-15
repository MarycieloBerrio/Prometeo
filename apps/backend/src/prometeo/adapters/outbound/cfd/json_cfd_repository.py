"""Read CFD manifests from data/simulations/cfd/manifests (never curated trials)."""

from __future__ import annotations

import json
from pathlib import Path

from prometeo.domain.cfd.model import CfdSimulation, CfdValidationStatus, ConvergenceStatus


class JsonCfdRepository:
    def __init__(self, manifests_dir: Path) -> None:
        self._dir = manifests_dir

    def list_all(self) -> list[CfdSimulation]:
        if not self._dir.is_dir():
            return []
        out: list[CfdSimulation] = []
        for path in sorted(self._dir.glob("CFD-*.json")):
            out.append(self._load(path))
        return out

    def get(self, simulation_id: str) -> CfdSimulation | None:
        path = self._dir / f"{simulation_id}.json"
        if not path.is_file():
            return None
        return self._load(path)

    def for_trial(self, trial_id: str) -> CfdSimulation | None:
        for sim in self.list_all():
            if sim.reference_trial_id == trial_id:
                return sim
        return None

    def _load(self, path: Path) -> CfdSimulation:
        raw = json.loads(path.read_text(encoding="utf-8"))
        field = (raw.get("result_files") or {}).get("field_sample")
        return CfdSimulation(
            simulation_id=raw["simulation_id"],
            reference_trial_id=raw["reference_trial_id"],
            solver=raw["solver"],
            solver_version=raw["solver_version"],
            model_type=raw["model_type"],
            inlet_velocity_m_s=float(raw["inlet_velocity_m_s"]),
            inlet_velocity_cm_s=float(raw["inlet_velocity_cm_s"]),
            oxygen_context_percent=(raw.get("oxygen_context") or {}).get("mole_percent"),
            mesh_cell_count=raw.get("mesh_cell_count"),
            residuals={k: float(v) for k, v in (raw.get("residuals") or {}).items()},
            mass_balance_error=raw.get("mass_balance_error"),
            mass_balance_status=str(raw.get("mass_balance_status", "not_verified")),
            mesh_independence=str(raw.get("mesh_independence", "not_demonstrated")),
            convergence_status=ConvergenceStatus(
                raw.get("convergence_status", "not_converged_or_not_run")
            ),
            validation_status=CfdValidationStatus(
                raw.get("validation_status", "pending_execution")
            ),
            field_sample_path=field,
            geometry_assumptions=tuple(raw.get("geometry_assumptions") or ()),
            limitations=tuple(raw.get("limitations") or ()),
            result_kind=str(raw.get("result_kind", "numerical_simulation")),
        )
