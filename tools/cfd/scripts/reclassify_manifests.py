"""Refresh the published B16 manifests and field exports from the ORIGINAL local runs.

No solver is re-run. For each case it:

1. re-reads ``log.foamRun`` and the iteration budget from the case's ``system/controlDict``
   (the old version of this script assumed endTime = 400) and re-classifies the run;
   the convergence status MUST come out identical to the published one, otherwise it aborts;
2. rewrites the convergence evidence with explicit SIMPLE-iteration wording
   ("Final SIMPLE iteration: 5000", never "5000 s");
3. records the patch volumetric-flux balance measured on the published solution by
   ``verify_numerics.py`` (experiment ``flux_published``), after checking that the U/p/phi files
   it post-processed are byte-identical to the case's final iteration;
4. re-exports the field at full mesh resolution and aborts unless every previously published
   (decimated) sample is reproduced exactly at its cell index.

A JSON change report is written next to the verification results.

Usage:  python tools/cfd/scripts/reclassify_manifests.py --run-id 2026-11-16-uy-audit
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPTS))

import generate_and_run as g  # noqa: E402
from convergence import classify_foam_run  # noqa: E402

VERIFICATION = g.ROOT / "data" / "simulations" / "cfd" / "verification"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def configured_end_time(case: Path) -> float:
    text = (case / "system" / "controlDict").read_text(encoding="utf-8")
    m = re.search(r"^endTime\s+([0-9.eE+-]+)\s*;", text, flags=re.M)
    if not m:
        raise RuntimeError(f"endTime not found in {case}/system/controlDict")
    return float(m.group(1))


def refresh_case(sim: str, vg: float, flux: dict[str, object]) -> dict[str, object]:
    case = g.CASES / sim
    man_path = g.MANIFESTS / f"{sim}.json"
    field_path = g.FIELDS / f"{sim}.json"
    manifest = json.loads(man_path.read_text(encoding="utf-8"))
    old_field = json.loads(field_path.read_text(encoding="utf-8"))
    before = {"manifest_sha256": _sha(man_path), "field_sha256": _sha(field_path)}

    log = (case / "log.foamRun").read_text(encoding="utf-8", errors="replace")
    end_time = configured_end_time(case)
    classified = classify_foam_run(log=log, returncode=0, configured_end_time=end_time)
    if classified.convergence_status != manifest["convergence_status"]:
        raise RuntimeError(
            f"{sim}: re-classification gives {classified.convergence_status} but the published "
            f"status is {manifest['convergence_status']} — refusing to change it here"
        )
    if classified.residuals != manifest["residuals"]:
        raise RuntimeError(f"{sim}: log residuals differ from the published manifest")

    latest = g._time_dirs(case)[-1]
    expected = flux.get("fields_sha256") or {}
    actual = {f: _sha(latest / f) for f in ("U", "p", "phi")}
    if expected != actual:
        raise RuntimeError(f"{sim}: post-processed fields are not the published final iteration")

    rel, status = g.balance_status(flux)  # type: ignore[arg-type]
    patch = {
        k: flux[k]
        for k in (
            "quantity",
            "inlet_phi_m3_s",
            "outlet_phi_m3_s",
            "imbalance_m3_s",
            "relative_imbalance",
            "sign_convention_ok",
            "status",
        )
        if k in flux
    }
    patch["tolerance"] = g.PATCH_BALANCE_TOLERANCE
    patch["method"] = (
        "foamPostProcess -func 'patchFlowRate(patch=inlet|outlet)' on a copy of the published "
        f"final iteration ({latest.name}); see data/simulations/cfd/verification/"
    )
    patch["precision_note"] = (
        "Fluxes are written with 9 significant digits, so relative imbalances near 1e-8 are at "
        "the output-precision floor."
    )

    manifest["convergence_evidence"] = classified.evidence
    manifest["final_simple_iteration"] = classified.final_iteration
    manifest.setdefault("solver_controls", {})["endTime_meaning"] = (
        "SIMPLE iteration budget (deltaT = 1 pseudo-time), not seconds"
    )
    manifest["patch_flow_balance"] = patch
    manifest["mass_balance_error"] = rel
    manifest["mass_balance_status"] = status
    limitations = [
        item
        for item in manifest.get("limitations", [])
        if item != "SIMPLE 'continuity errors ... global' is not a patch mass-flux balance."
    ]
    limitations.insert(
        4,
        "SIMPLE 'continuity errors ... global' is not a patch flux balance; the patch balance is "
        "a volumetric flux (no density) through the 5° wedge sector.",
    )
    manifest["limitations"] = limitations

    # Full-resolution field export from the same final iteration; verify the old samples.
    out = g.export_field_sample(case, sim, vg)
    if out is None:
        raise RuntimeError(f"{sim}: full-resolution export failed")
    new_field = json.loads(out.read_text(encoding="utf-8"))
    stride = int(old_field["downsample_stride"])
    reproduced = new_field["points"][::stride]
    if len(reproduced) != len(old_field["points"]) or any(
        a != b for a, b in zip(reproduced, old_field["points"], strict=True)
    ):
        out.write_text(json.dumps(old_field, indent=2), encoding="utf-8")  # restore
        raise RuntimeError(f"{sim}: full export does not reproduce the published samples")

    manifest["field_export"] = {
        "cells_exported": len(new_field["points"]),
        "mesh_cells": new_field["n_points_source"],
        "downsample_stride": 1,
        "previous_export": f"stride {stride} ({len(old_field['points'])} cells), reproduced exactly",
    }
    manifest["artifacts_refreshed_at"] = datetime.now(timezone.utc).isoformat()
    man_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return {
        "simulation_id": sim,
        "convergence_status_unchanged": manifest["convergence_status"],
        "final_simple_iteration": classified.final_iteration,
        "configured_end_iteration": end_time,
        "patch_balance": {"relative_imbalance": rel, "status": status},
        "field_cells_before_after": [len(old_field["points"]), len(new_field["points"])],
        "before": before,
        "after": {"manifest_sha256": _sha(man_path), "field_sha256": _sha(out)},
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run-id", required=True, help="verification run holding flux_published.json")
    args = ap.parse_args()
    flux_all = json.loads(
        (VERIFICATION / args.run_id / "flux_published.json").read_text(encoding="utf-8")
    )
    report = [refresh_case(sim, vg, flux_all[sim]) for sim, _trial, vg in g.B16_CASES]
    (VERIFICATION / args.run_id / "refresh_report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    for r in report:
        print(
            r["simulation_id"],
            r["convergence_status_unchanged"],
            r["patch_balance"],
            r["field_cells_before_after"],
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
