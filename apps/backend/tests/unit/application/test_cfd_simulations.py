"""CFD manifests are numerical_simulation records linked to curated trial IDs."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from prometeo.adapters.outbound.cfd.json_cfd_repository import JsonCfdRepository
from prometeo.application.use_cases.cfd_simulations import GetCfdSimulation, ListCfdSimulations
from prometeo.domain.cfd.model import CfdValidationStatus, ConvergenceStatus
from prometeo.domain.shared.errors import NotFoundError

DATA_DIR = Path(__file__).resolve().parents[5] / "data"
MANIFESTS = DATA_DIR / "simulations" / "cfd" / "manifests"
CURATED = DATA_DIR / "curated" / "trials.json"

B16_LINKS = {
    "CFD-B16-Vg072": ("BASS-II-B16-Vg072", 0.0072),
    "CFD-B16-Vg083": ("BASS-II-B16-Vg083", 0.0083),
    "CFD-B16-Vg167": ("BASS-II-B16-Vg167", 0.0167),
    "CFD-B16-Vg755": ("BASS-II-B16-Vg755", 0.0755),
}


@pytest.fixture
def repo() -> JsonCfdRepository:
    return JsonCfdRepository(MANIFESTS)


def test_cfd_linked_to_real_b16_trial_ids(repo: JsonCfdRepository) -> None:
    sims = repo.list_all()
    assert {s.simulation_id for s in sims} == set(B16_LINKS)
    for sim_id, (trial_id, vg) in B16_LINKS.items():
        sim = repo.get(sim_id)
        assert sim is not None
        assert sim.reference_trial_id == trial_id
        assert sim.inlet_velocity_m_s == pytest.approx(vg)
        assert sim.inlet_velocity_cm_s == pytest.approx(vg * 100)
        assert sim.result_kind == "numerical_simulation"
        assert repo.for_trial(trial_id) == sim


def test_unit_conversion_cm_s_to_m_s() -> None:
    assert pytest.approx(0.0072) == 0.72 / 100
    assert pytest.approx(0.0755) == 7.55 / 100


def test_manifest_validation_requires_convergence_fields(repo: JsonCfdRepository) -> None:
    for sim in repo.list_all():
        raw = json.loads((MANIFESTS / f"{sim.simulation_id}.json").read_text(encoding="utf-8"))
        assert raw["result_kind"] == "numerical_simulation"
        assert raw["not_experimental_observation"] is True
        assert "residuals" in raw
        assert "mass_balance_error" in raw
        assert raw["mesh_independence"] == "not_demonstrated"
        assert sim.convergence_status == ConvergenceStatus.CONVERGED
        assert sim.validation_status == CfdValidationStatus.NUMERICALLY_CHECKED


def test_experimental_and_simulated_are_distinct(repo: JsonCfdRepository) -> None:
    curated = json.loads(CURATED.read_text(encoding="utf-8"))
    curated_ids = {row["id"] for row in curated}
    for sim in repo.list_all():
        assert sim.simulation_id not in curated_ids
        assert sim.reference_trial_id in curated_ids
        trial = next(t for t in curated if t["id"] == sim.reference_trial_id)
        vf = next(r for r in trial["results"] if r["name"] == "flame_spread_rate")
        # CFD must not overwrite or invent Vf
        assert "flame_spread" not in json.dumps(sim.residuals)
        assert vf["value"]["value"] > 0


def test_missing_simulation_raises(repo: JsonCfdRepository) -> None:
    use_case = GetCfdSimulation(repo, DATA_DIR)
    with pytest.raises(NotFoundError):
        use_case.execute("CFD-DOES-NOT-EXIST")


def test_field_sample_loads_for_converged_cases(repo: JsonCfdRepository) -> None:
    use_case = GetCfdSimulation(repo, DATA_DIR)
    sample = use_case.field_sample("CFD-B16-Vg072")
    assert sample is not None
    assert sample.n_points_source == 1920
    assert sample.downsample_stride == 2
    assert len(sample.points) > 0
    assert "u_mag" in sample.points[0]
    assert sample.units["velocity"] == "m/s"


def test_list_filter_by_trial(repo: JsonCfdRepository) -> None:
    listed = ListCfdSimulations(repo).execute("BASS-II-B16-Vg755")
    assert len(listed) == 1
    assert listed[0].simulation_id == "CFD-B16-Vg755"
    assert ListCfdSimulations(repo).execute("BASS-II-NOPE") == []


def test_curated_trials_file_untouched_fingerprint() -> None:
    """Guard: CFD work must not alter curated NASA evidence JSON structure markers."""
    text = CURATED.read_text(encoding="utf-8")
    assert "BASS-II-B16-Vg072" in text
    assert "BASS-II-B16-Vg755" in text
    assert "simulations/cfd" not in text
    assert "numerical_simulation" not in text
    assert "flame_spread_rate" in text
