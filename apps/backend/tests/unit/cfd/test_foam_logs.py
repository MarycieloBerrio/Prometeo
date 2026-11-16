"""Parsers and checks for OpenFOAM logs / surfaceFieldValue output (no Docker required)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[5] / "tools" / "cfd" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from foam_logs import (  # noqa: E402
    final_iteration,
    iteration_table,
    parse_surface_field_value,
    patch_flow_balance,
    stationarity,
)

LOG = """Time = 1s

smoothSolver:  Solving for Ux, Initial residual = 1, Final residual = 0.01, No Iterations 2
smoothSolver:  Solving for Uy, Initial residual = 1, Final residual = 0.01, No Iterations 2
smoothSolver:  Solving for Uz, Initial residual = 1, Final residual = 0.01, No Iterations 2
GAMG:  Solving for p, Initial residual = 1, Final residual = 0.04, No Iterations 9
GAMG:  Solving for p, Initial residual = 0.5, Final residual = 0.02, No Iterations 4
time step continuity errors : sum local = 1e-05, global = -2e-07, cumulative = -2e-07
ExecutionTime = 0.01 s  ClockTime = 0 s

Time = 2s

smoothSolver:  Solving for Ux, Initial residual = 0.1, Final residual = 0.001, No Iterations 1
smoothSolver:  Solving for Uy, Initial residual = 0.3, Final residual = 0.002, No Iterations 1
smoothSolver:  Solving for Uz, Initial residual = 0.2, Final residual = 0.001, No Iterations 1
GAMG:  Solving for p, Initial residual = 0.05, Final residual = 0.002, No Iterations 5
GAMG:  Solving for p, Initial residual = 0.01, Final residual = 0.001, No Iterations 3
time step continuity errors : sum local = 1e-06, global = 3e-08, cumulative = -1.7e-07
"""


def test_iteration_table_takes_first_solve_and_counts_iterations() -> None:
    rows = iteration_table(LOG)
    assert [r["iteration"] for r in rows] == [1, 2]
    assert rows[1]["Uy"] == pytest.approx(0.3)
    assert rows[1]["p"] == pytest.approx(0.05)  # first pressure corrector, not the second
    assert rows[1]["continuity_global_abs"] == pytest.approx(3e-8)
    assert final_iteration(LOG) == 2


def test_surface_field_value_dat(tmp_path: Path) -> None:
    dat = tmp_path / "surfaceFieldValue.dat"
    dat.write_text(
        "# Region type : patch inlet\n# Faces  :      24\n# Area   :      6.24802554e-05\n"
        "# Time          \tsum(phi)\n4999            \t-4.71725926e-06\n"
        "5000            \t-4.71725927e-06\n",
        encoding="utf-8",
    )
    assert parse_surface_field_value(dat) == {4999: -4.71725926e-06, 5000: -4.71725927e-06}
    assert parse_surface_field_value(tmp_path / "missing.dat") == {}
    assert parse_surface_field_value(None) == {}


def test_patch_balance_uses_signed_volumetric_fluxes() -> None:
    ok = patch_flow_balance(-4.71725927e-06, 4.71725928e-06)
    assert ok["status"] == "computed"
    assert ok["sign_convention_ok"] is True
    assert ok["relative_imbalance"] == pytest.approx(2.12e-9, rel=1e-2)
    assert "volumetric" in str(ok["quantity"])
    assert "mass" not in str(ok["quantity"])


def test_patch_balance_never_invents_values() -> None:
    assert patch_flow_balance(None, 1.0)["status"] == "not_verified"
    assert patch_flow_balance(0.0, 0.0)["status"] == "not_verified"  # no division by zero
    wrong = patch_flow_balance(1e-6, -1e-6)  # outflow through the inlet: not accepted
    assert wrong["status"] == "not_verified"
    assert wrong["sign_convention_ok"] is False


def test_stationarity_window() -> None:
    rows: list[dict[str, float | int | None]] = [
        {
            "iteration": i,
            "Ux": 1e-9,
            "Uy": 5e-4,
            "Uz": 1e-9,
            "p": 1e-9,
            "dp_inlet_minus_outlet": 3.2e-3 * (1 + (1e-8 if i % 2 else 0)),
            "phi_outlet": 4.717e-6,
        }
        for i in range(1, 2001)
    ]
    s = stationarity(rows, 1000)
    assert s["iterations_in_window"] == 1000
    assert s["dp_max_relative_change"] == pytest.approx(1e-8, rel=1e-3)
    assert s["outlet_flux_max_relative_change"] == 0
    residuals = s["max_initial_residual_in_window"]
    assert isinstance(residuals, dict)
    assert residuals["Uy"] == pytest.approx(5e-4)
