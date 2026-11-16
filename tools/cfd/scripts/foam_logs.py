"""Pure parsers and checks for OpenFOAM 11 steady SIMPLE logs and surfaceFieldValue output.

Steady SIMPLE prints ``Time = 330s`` once per iteration: that counter is the SIMPLE iteration
(pseudo-time with deltaT = 1), NOT physical seconds. Everything here reports it as
``iteration`` with no unit.
"""

from __future__ import annotations

import math
import re
from pathlib import Path

_ITER_RE = re.compile(r"^Time = ([0-9.eE+-]+)s?\s*$", re.M)
_RES_RE = re.compile(r"Solving for (Ux|Uy|Uz|p), Initial residual = ([0-9.eE+-]+)")
_CONT_RE = re.compile(
    r"time step continuity errors : sum local = [0-9.eE+-]+, global = ([0-9.eE+-]+)"
)


def iteration_table(log: str) -> list[dict[str, float | int | None]]:
    """One row per SIMPLE iteration: first initial residual of Ux, Uy, Uz, p and |continuity|."""
    marks = list(_ITER_RE.finditer(log))
    rows: list[dict[str, float | int | None]] = []
    for k, m in enumerate(marks):
        block = log[m.end() : marks[k + 1].start() if k + 1 < len(marks) else len(log)]
        row: dict[str, float | int | None] = {
            "iteration": int(float(m.group(1))),
            "Ux": None,
            "Uy": None,
            "Uz": None,
            "p": None,
            "continuity_global_abs": None,
        }
        for name, value in _RES_RE.findall(block):
            if row[name] is None:  # first solve of the iteration (p has a second corrector)
                row[name] = float(value)
        cont = _CONT_RE.findall(block)
        if cont:
            row["continuity_global_abs"] = abs(float(cont[-1]))
        if row["Ux"] is not None or row["p"] is not None:
            rows.append(row)
    return rows


def final_iteration(log: str) -> int | None:
    marks = _ITER_RE.findall(log)
    return int(float(marks[-1])) if marks else None


def parse_surface_field_value(path: Path | None) -> dict[int, float]:
    """Read an OpenFOAM 11 surfaceFieldValue ``.dat`` file → {iteration: value}.

    Lines starting with '#' are headers; data lines are ``<time> <value> [...]``. Only the first
    value column is read (one field per function object here).
    """
    if path is None or not path.exists():
        return {}
    out: dict[int, float] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        try:
            out[int(float(parts[0]))] = float(parts[1])
        except ValueError:
            continue
    return out


def patch_flow_balance(phi_inlet: float | None, phi_outlet: float | None) -> dict[str, object]:
    """Integral volumetric balance from patch fluxes (sum of phi over each patch).

    OpenFOAM face normals point out of the domain, so inflow is negative on the inlet and
    outflow positive on the outlet. The balance is |phi_in + phi_out| / |phi_in|. In this
    incompressible solver phi is a VOLUMETRIC flux (m³/s through the 5° wedge sector) — it is
    not a mass flow and carries no density.
    """
    base: dict[str, object] = {
        "quantity": "volumetric flux sum(phi) [m^3/s] through the 5-degree wedge sector",
        "inlet_phi_m3_s": phi_inlet,
        "outlet_phi_m3_s": phi_outlet,
    }
    if phi_inlet is None or phi_outlet is None:
        return {**base, "status": "not_verified", "reason": "patch flux not available"}
    if phi_inlet == 0 or not (math.isfinite(phi_inlet) and math.isfinite(phi_outlet)):
        return {**base, "status": "not_verified", "reason": "zero or non-finite inlet flux"}
    signs_ok = phi_inlet < 0 < phi_outlet
    imbalance = phi_inlet + phi_outlet
    return {
        **base,
        "status": "computed" if signs_ok else "not_verified",
        "sign_convention_ok": signs_ok,
        "imbalance_m3_s": imbalance,
        "relative_imbalance": abs(imbalance) / abs(phi_inlet),
        **({} if signs_ok else {"reason": "unexpected flux signs (inlet must be < 0 < outlet)"}),
    }


def _max_rel_change(values: list[float]) -> float | None:
    vals = [v for v in values if v is not None]
    if len(vals) < 2 or vals[-1] == 0:
        return None
    ref = vals[-1]
    return max(abs(v - ref) for v in vals) / abs(ref)


def stationarity(rows: list[dict[str, float | int | None]], window: int) -> dict[str, object]:
    """Relative drift of the quantities of interest over the final ``window`` iterations."""
    if not rows:
        return {"window_iterations": window, "available": False}
    last_it = int(rows[-1]["iteration"] or 0)
    tail = [r for r in rows if int(r["iteration"] or 0) > last_it - window]
    dp = [r.get("dp_inlet_minus_outlet") for r in tail]
    q_out = [r.get("phi_outlet") for r in tail]
    return {
        "window_iterations": window,
        "available": True,
        "iterations_in_window": len(tail),
        "dp_max_relative_change": _max_rel_change([v for v in dp if isinstance(v, float)]),
        "outlet_flux_max_relative_change": _max_rel_change(
            [v for v in q_out if isinstance(v, float)]
        ),
        "max_initial_residual_in_window": {
            k: max((float(r[k]) for r in tail if r.get(k) is not None), default=None)
            for k in ("Ux", "Uy", "Uz", "p")
        },
    }
