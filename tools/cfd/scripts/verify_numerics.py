#!/usr/bin/env python3
"""Controlled numerical-verification experiments for the B16 OpenFOAM cases.

Never touches the published results: inputs are COPIED from the original case directories
into ``tools/cfd/openfoam/verification_runs/<run_id>/`` (gitignored runtime) and every output
is written to ``data/simulations/cfd/verification/<run_id>/``. The four published manifests,
fields and their convergence statuses are not modified by this script.

Experiments
-----------
flux_published   Patch volumetric flux (sum of phi) on inlet/outlet of the PUBLISHED solutions
                 (copy of each original case at its final iteration; no re-solve).
component_keys   Vg755 rerun with ``residualControl { Ux 1e-6; Uz 1e-6; p 1e-6; }`` to test
                 whether OpenFOAM 11 honours per-component keys (it should not: keys are
                 matched against field names).
extended_budget  All four cases rerun with the ORIGINAL residualControl (U 1e-4, p 1e-4) but a
                 larger iteration budget, logging per-iteration residuals, patch fluxes and
                 inlet/outlet mean kinematic pressure.

Usage:  python tools/cfd/scripts/verify_numerics.py --run-id 2026-11-16-uy-audit [--only ...]
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import csv
import hashlib
import json
import math
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import generate_and_run as g  # noqa: E402
from convergence import classify_foam_run  # noqa: E402
from foam_logs import (  # noqa: E402
    iteration_table,
    parse_surface_field_value,
    patch_flow_balance,
    stationarity,
)

RUNS = g.ROOT / "tools" / "cfd" / "openfoam" / "verification_runs"
OUT = g.ROOT / "data" / "simulations" / "cfd" / "verification"
WEDGE_RAD = math.radians(g.WEDGE_DEG)

MONITOR_FUNCTIONS = (
    "functions\n{\n"
    "    #includeFunc patchFlowRate(patch=inlet)\n"
    "    #includeFunc patchFlowRate(patch=outlet)\n"
    "    #includeFunc patchAverage(patch=inlet, fields=(p))\n"
    "    #includeFunc patchAverage(patch=outlet, fields=(p))\n"
    "}\n"
)

# Pre-declared acceptance thresholds (written before the runs; see README in the output dir).
CRITERIA = {
    "window_iterations": 1000,
    "qoi_relative_change_max": 1e-6,  # Δp and outlet flux over the final window
    "residual_max_Ux_Uz_p": 1e-6,  # final initial residuals of the non-null components and p
    "patch_flux_relative_imbalance_max": 1e-6,
    "uy_over_vg_max": 1e-9,  # Uy must be physically null in the axisymmetric wedge
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stage_inputs(src: Path, dst: Path) -> None:
    """Copy only the case inputs (0/, constant/, system/) — never results."""
    if dst.exists():
        shutil.rmtree(dst)
    dst.mkdir(parents=True)
    for sub in ("0", "constant", "system"):
        shutil.copytree(src / sub, dst / sub, ignore=shutil.ignore_patterns("polyMesh"))
    for stray in (dst / "system").glob("flowRate_*"):
        stray.unlink()


def stage_published(src: Path, dst: Path) -> Path:
    """Copy a published case INCLUDING its final iteration and mesh, for post-processing only."""
    if dst.exists():
        shutil.rmtree(dst)
    latest = g._time_dirs(src)[-1]
    dst.mkdir(parents=True)
    for sub in ("constant", "system"):
        shutil.copytree(src / sub, dst / sub)
    shutil.copytree(latest, dst / latest.name)
    for stray in (dst / "system").glob("flowRate_*"):
        stray.unlink()
    return dst / latest.name


def set_control(case: Path, end_time: int, write_interval: int) -> None:
    path = case / "system" / "controlDict"
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"^endTime\s+[^;]+;", f"endTime         {end_time};", text, flags=re.M)
    text = re.sub(
        r"^writeInterval\s+[^;]+;", f"writeInterval   {write_interval};", text, flags=re.M
    )
    text = re.sub(r"^functions\s*\{.*?^\}\s*", "", text, flags=re.M | re.S)
    marker = "// ****"
    idx = text.rfind(marker)
    text = (
        text[:idx] + MONITOR_FUNCTIONS + "\n" + text[idx:]
        if idx != -1
        else text + MONITOR_FUNCTIONS
    )
    path.write_text(text, encoding="utf-8")


def set_residual_control(case: Path, entries: dict[str, float]) -> None:
    path = case / "system" / "fvSolution"
    text = path.read_text(encoding="utf-8")
    body = "".join(f"        {k:<15} {v:g};\n" for k, v in entries.items())
    new = "    residualControl\n    {\n" + body + "    }"
    text, n = re.subn(r"    residualControl\s*\{[^}]*\}", new, text)
    if n != 1:
        raise RuntimeError(f"residualControl block not found in {path}")
    path.write_text(text, encoding="utf-8")


def run_case(case: Path, timeout: int) -> int:
    script = (
        "blockMesh > log.blockMesh 2>&1 || exit 2; "
        "foamRun > log.foamRun 2>&1; rc=$?; "
        "checkMesh > log.checkMesh 2>&1 || true; exit $rc"
    )
    proc = g._docker_bash(case, script, timeout=timeout)
    return proc.returncode


def postprocess_flux(case: Path, time_name: str) -> dict[str, float | None]:
    script = (
        f"foamPostProcess -func 'patchFlowRate(patch=inlet)' -time {time_name} "
        "> log.pp_flow_inlet 2>&1; "
        f"foamPostProcess -func 'patchFlowRate(patch=outlet)' -time {time_name} "
        "> log.pp_flow_outlet 2>&1; "
        f"foamPostProcess -func 'patchAverage(patch=inlet, fields=(p))' -time {time_name} "
        "> log.pp_p_inlet 2>&1; "
        f"foamPostProcess -func 'patchAverage(patch=outlet, fields=(p))' -time {time_name} "
        "> log.pp_p_outlet 2>&1"
    )
    g._docker_bash(case, script, timeout=300)
    pp = case / "postProcessing"
    return {
        "phi_inlet": _last(parse_surface_field_value(_dat(pp, "patchFlowRate(patch=inlet)"))),
        "phi_outlet": _last(parse_surface_field_value(_dat(pp, "patchFlowRate(patch=outlet)"))),
        "p_inlet": _last(
            parse_surface_field_value(_dat(pp, "patchAverage(patch=inlet,fields=(p))"))
        ),
        "p_outlet": _last(
            parse_surface_field_value(_dat(pp, "patchAverage(patch=outlet,fields=(p))"))
        ),
    }


def _dat(pp: Path, func: str) -> Path | None:
    """surfaceFieldValue output for a packaged function (directory name has no spaces)."""
    if not pp.exists():
        return None
    wanted = func.replace(" ", "")
    for d in pp.iterdir():
        if d.name.replace(" ", "") == wanted:
            files = sorted(d.rglob("*.dat"))
            return files[-1] if files else None
    return None


def _last(series: dict[int, float]) -> float | None:
    return series[max(series)] if series else None


def analytic_inlet_flux(vg: float) -> float:
    """|phi| expected through the 5° wedge inlet: Vg × (θ/2)(Ro² − Ri²)."""
    return vg * 0.5 * WEDGE_RAD * (g.DUCT_OUTER_RADIUS_M**2 - g.ROD_RADIUS_M**2)


def exp_flux_published(
    run_dir: Path, out: Path, sims: list[tuple[str, str, float]]
) -> dict[str, object]:
    results: dict[str, object] = {}
    for sim, _trial, vg in sims:
        src = g.CASES / sim
        case = run_dir / "flux_published" / sim
        latest = stage_published(src, case)
        vals = postprocess_flux(case, latest.name)
        balance = patch_flow_balance(vals["phi_inlet"], vals["phi_outlet"])
        results[sim] = {
            "source_case": f"tools/cfd/openfoam/cases/{sim}",
            "final_simple_iteration": int(float(latest.name)),
            "fields_sha256": {f: _sha256(latest / f) for f in ("U", "p", "phi")},
            **balance,
            "analytic_inlet_flux_m3_s": analytic_inlet_flux(vg),
            "mean_p_inlet_m2_s2": vals["p_inlet"],
            "mean_p_outlet_m2_s2": vals["p_outlet"],
        }
        print(
            f"[flux_published] {sim}: {balance.get('status')} rel={balance.get('relative_imbalance')}"
        )
    (out / "flux_published.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    return results


def _run_variant(
    run_dir: Path,
    out: Path,
    exp: str,
    sim: str,
    vg: float,
    end_time: int,
    residual_control: dict[str, float],
) -> dict[str, object]:
    case = run_dir / exp / sim
    stage_inputs(g.CASES / sim, case)
    set_control(case, end_time=end_time, write_interval=end_time)
    set_residual_control(case, residual_control)
    rc = run_case(case, timeout=7200)
    log = (case / "log.foamRun").read_text(encoding="utf-8", errors="replace")
    classified = classify_foam_run(log=log, returncode=rc, configured_end_time=float(end_time))
    table = iteration_table(log)
    pp = case / "postProcessing"
    phi_in = parse_surface_field_value(_dat(pp, "patchFlowRate(patch=inlet)"))
    phi_out = parse_surface_field_value(_dat(pp, "patchFlowRate(patch=outlet)"))
    p_in = parse_surface_field_value(_dat(pp, "patchAverage(patch=inlet,fields=(p))"))
    p_out = parse_surface_field_value(_dat(pp, "patchAverage(patch=outlet,fields=(p))"))
    for row in table:
        it = row["iteration"]
        row["phi_inlet"] = phi_in.get(it)
        row["phi_outlet"] = phi_out.get(it)
        row["dp_inlet_minus_outlet"] = p_in[it] - p_out[it] if it in p_in and it in p_out else None
    sdir = out / exp
    sdir.mkdir(parents=True, exist_ok=True)
    _write_csv(sdir / f"{sim}_history.csv", table)
    last = table[-1] if table else {}
    times = g._time_dirs(case)
    uy_max = None
    if times:
        parsed = (
            g._parse_cell_fields(times[-1] / "C", times[-1] / "U", times[-1] / "p")
            if (times[-1] / "C").exists()
            else None
        )
        if parsed is None:
            g._docker_bash(
                case,
                f"postProcess -func writeCellCentres -time {times[-1].name} > log.writeC 2>&1",
                300,
            )
            parsed = g._parse_cell_fields(times[-1] / "C", times[-1] / "U", times[-1] / "p")
        if parsed:
            uy_max = max(abs(u[1]) for u in parsed[1])
    summary = {
        "experiment": exp,
        "simulation_id": sim,
        "inlet_velocity_m_s": vg,
        "residualControl": residual_control,
        "configured_end_iteration": end_time,
        "returncode": rc,
        "solver_announced_convergence": classified.solver_announced_convergence,
        "convergence_status": classified.convergence_status,
        "evidence": classified.evidence,
        "final_simple_iteration": last.get("iteration"),
        "final_initial_residuals": {k: last.get(k) for k in ("Ux", "Uy", "Uz", "p")},
        "final_continuity_global_abs": classified.continuity_global_abs,
        "max_abs_uy_m_s": uy_max,
        "uy_over_vg": (uy_max / vg) if uy_max is not None else None,
        "patch_flux": patch_flow_balance(last.get("phi_inlet"), last.get("phi_outlet")),
        "analytic_inlet_flux_m3_s": analytic_inlet_flux(vg),
        "stationarity": stationarity(table, CRITERIA["window_iterations"]),
        "history_csv": f"{exp}/{sim}_history.csv",
    }
    (sdir / f"{sim}_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(
        f"[{exp}] {sim}: rc={rc} status={summary['convergence_status']} it={summary['final_simple_iteration']}"
    )
    return summary


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    keys = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run-id", required=True)
    ap.add_argument(
        "--only", nargs="*", choices=["flux_published", "component_keys", "extended_budget"]
    )
    ap.add_argument("--extended-end", type=int, default=30000)
    args = ap.parse_args()
    if not g.docker_available():
        print("Docker is not available: no experiment was run.", file=sys.stderr)
        return 2
    run_dir = RUNS / args.run_id
    out = OUT / args.run_id
    out.mkdir(parents=True, exist_ok=True)
    todo = set(args.only or ["flux_published", "component_keys", "extended_budget"])
    meta = {
        "run_id": args.run_id,
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "docker_image": g.DOCKER_IMAGE,
        "criteria": CRITERIA,
        "experiments": sorted(todo),
    }
    sims = list(g.B16_CASES)
    if "flux_published" in todo:
        exp_flux_published(run_dir, out, sims)
    jobs = []
    with cf.ThreadPoolExecutor(max_workers=5) as pool:
        if "component_keys" in todo:
            jobs.append(
                pool.submit(
                    _run_variant,
                    run_dir,
                    out,
                    "component_keys",
                    "CFD-B16-Vg755",
                    0.0755,
                    5000,
                    {"Ux": 1e-6, "Uz": 1e-6, "p": 1e-6},
                )
            )
        if "extended_budget" in todo:
            for sim, _trial, vg in sims:
                jobs.append(
                    pool.submit(
                        _run_variant,
                        run_dir,
                        out,
                        "extended_budget",
                        sim,
                        vg,
                        args.extended_end,
                        {"p": 1e-4, "U": 1e-4},
                    )
                )
        for j in jobs:
            j.result()
    meta["finished_utc"] = datetime.now(timezone.utc).isoformat()
    (out / "run_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
