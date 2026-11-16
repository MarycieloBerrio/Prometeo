"""Integrity of the published CFD artefacts (data/simulations/cfd) and of the NASA inputs."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[5]
CFD = ROOT / "data" / "simulations" / "cfd"
CASES = ("CFD-B16-Vg072", "CFD-B16-Vg083", "CFD-B16-Vg167", "CFD-B16-Vg755")
# Published statuses: changing one needs a new run and a reviewed decision, not a refactor.
EXPECTED_STATUS = {
    "CFD-B16-Vg072": "converged",
    "CFD-B16-Vg083": "converged",
    "CFD-B16-Vg167": "max_iterations_reached",
    "CFD-B16-Vg755": "max_iterations_reached",
}


def _manifest(sim: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(
        (CFD / "manifests" / f"{sim}.json").read_text(encoding="utf-8")
    )
    return data


@pytest.mark.parametrize("sim", CASES)
def test_convergence_status_is_unchanged_and_evidence_backed(sim: str) -> None:
    m = _manifest(sim)
    assert m["convergence_status"] == EXPECTED_STATUS[sim]
    evidence = str(m["convergence_evidence"])
    if m["convergence_status"] == "converged":
        assert m["solver_announced_convergence"] is True
        assert "SIMPLE solution converged in" in evidence
    else:
        assert m["solver_announced_convergence"] is False
        assert m["validation_status"] == "solver_executed"


@pytest.mark.parametrize("sim", CASES)
def test_iterations_are_never_reported_as_seconds(sim: str) -> None:
    m = _manifest(sim)
    evidence = str(m["convergence_evidence"])
    assert "Final Time" not in evidence
    assert "5000s" not in evidence
    assert isinstance(m["final_simple_iteration"], int)
    if m["convergence_status"] == "max_iterations_reached":
        assert f"Final SIMPLE iteration: {m['final_simple_iteration']}" in evidence


@pytest.mark.parametrize("sim", CASES)
def test_patch_balance_is_volumetric_and_within_tolerance_when_verified(sim: str) -> None:
    m = _manifest(sim)
    patch = m["patch_flow_balance"]
    assert isinstance(patch, dict)
    if m["mass_balance_status"] == "verified":
        assert "volumetric" in patch["quantity"]
        assert "mass flow" not in patch["quantity"]
        assert patch["inlet_phi_m3_s"] < 0 < patch["outlet_phi_m3_s"]
        rel = abs(patch["inlet_phi_m3_s"] + patch["outlet_phi_m3_s"]) / abs(
            patch["inlet_phi_m3_s"]
        )
        assert rel == pytest.approx(m["mass_balance_error"])
        assert rel <= patch["tolerance"] <= 1e-6
    else:
        assert m["mass_balance_error"] is None


@pytest.mark.parametrize("sim", CASES)
def test_mesh_independence_is_not_claimed(sim: str) -> None:
    assert _manifest(sim)["mesh_independence"] == "not_demonstrated"


@pytest.mark.parametrize("sim", CASES)
def test_full_resolution_field_export(sim: str) -> None:
    m = _manifest(sim)
    field = json.loads((CFD / "fields" / f"{sim}.json").read_text(encoding="utf-8"))
    nr, nt, nz = field["mesh_resolution_nr_ntheta_nz"]
    assert len(field["points"]) == field["n_points_source"] == m["mesh_cell_count"] == nr * nt * nz
    assert field["downsample_stride"] == 1
    zs = {round(p["z"], 9) for p in field["points"]}
    rs = {round(math.hypot(p["x"], p["y"]), 9) for p in field["points"]}
    assert (len(rs), len(zs)) == (nr, nz)
    for p in field["points"]:
        assert all(math.isfinite(p[k]) for k in ("x", "y", "z", "ux", "uy", "uz", "u_mag", "p"))
        assert p["u_mag"] == pytest.approx(math.sqrt(p["ux"] ** 2 + p["uy"] ** 2 + p["uz"] ** 2))


def test_nasa_flame_spread_values_are_untouched() -> None:
    trials = json.loads((ROOT / "data" / "curated" / "trials.json").read_text(encoding="utf-8"))
    vf = {t["id"]: t["results"][0]["value"]["value"] for t in trials if t.get("sample_id") == "B16"}
    assert vf == {
        "BASS-II-B16-Vg072": 0.0568,
        "BASS-II-B16-Vg083": 0.0699,
        "BASS-II-B16-Vg167": 0.0762,
        "BASS-II-B16-Vg755": 0.0678,
    }
