"""Unit tests for OpenFOAM SIMPLE run classification (no Docker required)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[5] / "tools" / "cfd" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from convergence import RunOutcome, classify_foam_run  # noqa: E402


def _line(name: str, residual: str) -> str:
    return f"smoothSolver:  Solving for {name}, Initial residual = {residual}\n"


CONVERGED_LOG = (
    "Time = 329s\n"
    + _line("Uy", "0.00010357204")
    + "time step continuity errors : sum local = 1e-9, global = -1.5835491e-10\n"
    + "Time = 330s\n"
    + _line("Ux", "2.004426e-08")
    + _line("Uy", "9.9428646e-05")
    + _line("Uz", "6.6227773e-09")
    + "GAMG:  Solving for p, Initial residual = 2.4565301e-09\n"
    + "time step continuity errors : sum local = 3e-10, global = -1.3546133e-10\n"
    + "SIMPLE solution converged in 330 iterations\n"
    + "End\n"
)

MAX_ITERS_LOG = (
    "Time = 399s\n"
    + _line("Uy", "0.00034836394")
    + "Time = 400s\n"
    + _line("Ux", "6.1766346e-09")
    + _line("Uy", "0.00017604548")
    + _line("Uz", "1.3016574e-09")
    + "GAMG:  Solving for p, Initial residual = 4.0036347e-09\n"
    + "time step continuity errors : sum local = 5e-10, global = -5.2534417e-11\n"
    + "End\n"
)


def test_announced_convergence_is_converged() -> None:
    result = classify_foam_run(log=CONVERGED_LOG, returncode=0, configured_end_time=5000)
    assert result.outcome == RunOutcome.CONVERGED
    assert result.convergence_status == "converged"
    assert result.validation_status == "numerically_checked"
    assert result.solver_announced_convergence is True
    assert "SIMPLE solution converged in 330" in result.evidence
    assert result.residuals["Uy"] == pytest.approx(9.9428646e-05)
    assert result.continuity_global_abs == pytest.approx(1.3546133e-10)


def test_end_without_announcement_is_max_iterations() -> None:
    result = classify_foam_run(log=MAX_ITERS_LOG, returncode=0, configured_end_time=400)
    assert result.outcome == RunOutcome.MAX_ITERATIONS_REACHED
    assert result.convergence_status == "max_iterations_reached"
    assert result.validation_status == "solver_executed"
    assert result.solver_announced_convergence is False
    assert "No 'SIMPLE solution converged'" in result.evidence
    assert result.residuals["Uy"] == pytest.approx(0.00017604548)


def test_done_echo_alone_is_not_convergence() -> None:
    """Regression: container stdout DONE must never upgrade status."""
    fake = MAX_ITERS_LOG + "\nDONE\n"
    result = classify_foam_run(log=fake, returncode=0, configured_end_time=400)
    assert result.outcome == RunOutcome.MAX_ITERATIONS_REACHED
    assert result.convergence_status != "converged"


def test_nonzero_exit_is_solver_failed() -> None:
    result = classify_foam_run(log="foamRun crashed\n", returncode=3)
    assert result.outcome == RunOutcome.SOLVER_FAILED
    assert result.convergence_status == "solver_failed"
    assert result.validation_status == "pending_execution"


def test_iteration_counter_is_not_reported_as_seconds() -> None:
    """Steady SIMPLE prints 'Time = 400s'; that is an iteration count, not physical time."""
    result = classify_foam_run(log=MAX_ITERS_LOG, returncode=0, configured_end_time=400)
    assert result.final_iteration == 400
    assert "Final SIMPLE iteration: 400" in result.evidence
    assert "not seconds" in result.evidence
    assert "400s" not in result.evidence
    assert "Final Time" not in result.evidence


def test_velocity_criterion_is_described_as_largest_component() -> None:
    result = classify_foam_run(log=MAX_ITERS_LOG, returncode=0, configured_end_time=400)
    assert "largest velocity-component residual" in result.evidence


def test_not_run() -> None:
    result = classify_foam_run(log="", returncode=None)
    assert result.outcome == RunOutcome.NOT_RUN
    assert result.convergence_status == "not_run"
    assert result.validation_status == "pending_execution"
