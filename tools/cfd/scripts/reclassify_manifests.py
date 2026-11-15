"""Reclassify existing foamRun logs into manifests (no solver re-run)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPTS))

from convergence import classify_foam_run  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
CASES = ROOT / "tools" / "cfd" / "openfoam" / "cases"
MANIFESTS = ROOT / "data" / "simulations" / "cfd" / "manifests"


def main() -> int:
    end_time = float(sys.argv[1]) if len(sys.argv) > 1 else 400.0
    for mid in (
        "CFD-B16-Vg072",
        "CFD-B16-Vg083",
        "CFD-B16-Vg167",
        "CFD-B16-Vg755",
    ):
        logp = CASES / mid / "log.foamRun"
        manp = MANIFESTS / f"{mid}.json"
        log = logp.read_text(encoding="utf-8", errors="replace") if logp.exists() else ""
        classified = classify_foam_run(
            log=log,
            returncode=0 if log else None,
            configured_end_time=end_time,
        )
        manifest = json.loads(manp.read_text(encoding="utf-8"))
        manifest["convergence_status"] = classified.convergence_status
        manifest["validation_status"] = classified.validation_status
        manifest["solver_announced_convergence"] = classified.solver_announced_convergence
        manifest["convergence_evidence"] = classified.evidence
        manifest["residuals"] = classified.residuals
        manifest["continuity_global_abs"] = classified.continuity_global_abs
        manifest["continuity_global_note"] = (
            "Absolute value of OpenFOAM SIMPLE 'time step continuity errors ... global' "
            "from the final iteration — not a patch-integrated mass/volume flux balance."
        )
        manifest["mass_balance_error"] = None
        manifest["mass_balance_status"] = "not_verified"
        manifest["mesh_quality"] = manifest.get("mesh_quality") or {"status": "not_verified"}
        limitations = list(manifest.get("limitations") or [])
        note = (
            "Fields may exist from a finished run, but residual convergence was not announced "
            "by OpenFOAM — do not treat this case as converged."
        )
        if classified.convergence_status != "converged" and note not in limitations:
            limitations.append(note)
        manifest["limitations"] = limitations
        manp.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        print(mid, classified.convergence_status, classified.validation_status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
