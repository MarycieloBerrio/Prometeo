"""Pure classification of OpenFOAM SIMPLE run outcomes.

DONE / container exit code alone must NEVER imply residual convergence.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum


class RunOutcome(StrEnum):
    NOT_RUN = "not_run"
    SOLVER_FAILED = "solver_failed"
    MAX_ITERATIONS_REACHED = "max_iterations_reached"
    CONVERGED = "converged"


# Maps to API / manifest convergence_status values.
OUTCOME_TO_CONVERGENCE_STATUS = {
    RunOutcome.NOT_RUN: "not_run",
    RunOutcome.SOLVER_FAILED: "solver_failed",
    RunOutcome.MAX_ITERATIONS_REACHED: "max_iterations_reached",
    RunOutcome.CONVERGED: "converged",
}


@dataclass(frozen=True, slots=True)
class ClassifiedRun:
    outcome: RunOutcome
    convergence_status: str
    validation_status: str
    solver_announced_convergence: bool
    final_time_s: float | None
    residuals: dict[str, float]
    continuity_global_abs: float | None
    evidence: str


_CONVERGED_RE = re.compile(r"SIMPLE solution converged in (\d+) iterations", re.I)
_TIME_RE = re.compile(r"^Time = ([0-9.]+)s?\s*$", re.M)
_RESIDUAL_RE = {
    name: re.compile(rf"Solving for {name}, Initial residual = ([0-9.eE+-]+)")
    for name in ("Ux", "Uy", "Uz", "p")
}
_CONTINUITY_RE = re.compile(
    r"time step continuity errors : sum local = ([0-9.eE+-]+), global = ([0-9.eE+-]+)"
)


def parse_residuals(log: str) -> dict[str, float]:
    out: dict[str, float] = {}
    for name, pattern in _RESIDUAL_RE.items():
        matches = pattern.findall(log)
        if matches:
            out[name] = float(matches[-1])
    return out


def parse_continuity_global_abs(log: str) -> float | None:
    matches = _CONTINUITY_RE.findall(log)
    if not matches:
        return None
    return abs(float(matches[-1][1]))


def parse_final_time(log: str) -> float | None:
    times = _TIME_RE.findall(log)
    if not times:
        return None
    return float(times[-1])


def classify_foam_run(
    *,
    log: str,
    returncode: int | None,
    configured_end_time: float | None = None,
) -> ClassifiedRun:
    """Classify a foamRun log.

    Convergence requires an explicit OpenFOAM announcement
    (``SIMPLE solution converged``). Hitting endTime without that message is
    ``max_iterations_reached``, never ``converged``.
    """
    residuals = parse_residuals(log)
    continuity = parse_continuity_global_abs(log)
    final_time = parse_final_time(log)
    announced = bool(_CONVERGED_RE.search(log))

    if returncode is None and not log.strip():
        return ClassifiedRun(
            outcome=RunOutcome.NOT_RUN,
            convergence_status=OUTCOME_TO_CONVERGENCE_STATUS[RunOutcome.NOT_RUN],
            validation_status="pending_execution",
            solver_announced_convergence=False,
            final_time_s=None,
            residuals={},
            continuity_global_abs=None,
            evidence="Solver was not executed.",
        )

    if returncode is not None and returncode != 0:
        return ClassifiedRun(
            outcome=RunOutcome.SOLVER_FAILED,
            convergence_status=OUTCOME_TO_CONVERGENCE_STATUS[RunOutcome.SOLVER_FAILED],
            validation_status="pending_execution",
            solver_announced_convergence=False,
            final_time_s=final_time,
            residuals=residuals,
            continuity_global_abs=continuity,
            evidence=f"Solver process exited with code {returncode}.",
        )

    if announced:
        m = _CONVERGED_RE.search(log)
        iters = m.group(1) if m else "?"
        return ClassifiedRun(
            outcome=RunOutcome.CONVERGED,
            convergence_status=OUTCOME_TO_CONVERGENCE_STATUS[RunOutcome.CONVERGED],
            validation_status="numerically_checked",
            solver_announced_convergence=True,
            final_time_s=final_time,
            residuals=residuals,
            continuity_global_abs=continuity,
            evidence=f"OpenFOAM announced: SIMPLE solution converged in {iters} iterations.",
        )

    # Successful exit without convergence announcement → max iterations / endTime.
    end_note = ""
    if configured_end_time is not None and final_time is not None:
        end_note = f" Final Time={final_time:g}s; configured endTime={configured_end_time:g}."
    elif final_time is not None:
        end_note = f" Final Time={final_time:g}s."

    uy = residuals.get("Uy")
    uy_note = ""
    if uy is not None:
        uy_note = f" Final Uy initial residual={uy:.6g} (residualControl U=1e-4)."

    return ClassifiedRun(
        outcome=RunOutcome.MAX_ITERATIONS_REACHED,
        convergence_status=OUTCOME_TO_CONVERGENCE_STATUS[RunOutcome.MAX_ITERATIONS_REACHED],
        validation_status="solver_executed",
        solver_announced_convergence=False,
        final_time_s=final_time,
        residuals=residuals,
        continuity_global_abs=continuity,
        evidence=(
            "No 'SIMPLE solution converged' announcement in log; "
            "run finished at endTime / max iterations."
            + end_note
            + uy_note
        ),
    )
