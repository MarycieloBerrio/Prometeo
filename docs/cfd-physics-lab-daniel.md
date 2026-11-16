# CFD Physics Lab — implementation notes (Daniel)

Branch: `feat/daniel-cfd-physics-lab`

## What was delivered

1. Reproducible OpenFOAM 11 axial annular cases for four B16 Vg values.
2. Manifests + downsampled field JSON under `data/simulations/cfd/` (separate from curated trials).
3. Backend API `/api/v1/cfd/*` + Compare Lab Physics Lab UI with Numerical Verification and
   deterministic A/B/C/D scientific interpretation.

## Convergence audit (pre-merge)

Classification uses only OpenFOAM's `SIMPLE solution converged` announcement.
Finishing at `endTime` without that line is `max_iterations_reached` / `solver_executed`.
`DONE` / container exit alone never implies convergence.

See `tools/cfd/scripts/convergence.py` and unit tests under
`apps/backend/tests/unit/cfd/test_convergence_classification.py`.

| Case | Executed | Converged | validation_status | continuity_global (log, not patch flux) | Mesh (checkMesh) | Patch flux balance |
|---|---|---|---|---|---|---|
| CFD-B16-Vg072 | yes (330 SIMPLE iterations) | **yes** — `SIMPLE solution converged in 330 iterations` | numerically_checked | 1.35e-10 | mesh_ok | verified (4.4e-9) |
| CFD-B16-Vg083 | yes (619 SIMPLE iterations) | **yes** — `SIMPLE solution converged in 619 iterations` | numerically_checked | 8.97e-12 | mesh_ok | verified (3.9e-9) |
| CFD-B16-Vg167 | yes (final SIMPLE iteration 5000) | **no** — max_iterations_reached; final Uy initial residual > 1e-4 | solver_executed | 1.99e-11 | mesh_ok | verified (9.6e-9) |
| CFD-B16-Vg755 | yes (final SIMPLE iteration 5000) | **no** — max_iterations_reached; final Uy initial residual > 1e-4 | solver_executed | 4.06e-11 | mesh_ok | verified (2.1e-9) |

UI screenshots (honest labels): `docs/assets/cfd-audit/`.

## Scientific limits (do not dilute)

- Not a reproduction of BASS-II combustion.
- Does not invent absolute pressure.
- Does not generate Vf, temperature, or O₂ fields.
- Does not claim 0g vs 1g from isothermal forced flow.
- Mesh independence documented per case (`not_demonstrated` unless a base/fine study reports otherwise).
- Field viewer shows a **scalar** sampled field (|U| or p); no streamlines fabricated from |U|.

"Time = 5000" in a steady SIMPLE log is the iteration counter (deltaT = 1 pseudo-time), not
seconds. Patch balance = abs(phi_in + phi_out) / abs(phi_in) of the volumetric flux through the
5-degree wedge (tolerance 1e-6), measured on the published solutions on 2026-11-16.

### Numerical verification 2026-11-16 (`data/simulations/cfd/verification/2026-11-16-uy-audit/`)

- OpenFOAM 11 checks the U criterion on the **largest** component residual; `residualControl`
  keys `Ux`/`Uz` are silently ignored (a test run "converged" on `p` alone).
- In all four cases the deciding component is **Uy**, the analytically null wedge-tangential
  component (abs(Uy) ~ 1e-15 Vg). Rerunning Vg167/Vg755 to 30000 iterations with the unchanged
  criterion: Uy stays at 2e-4 to 1e-3, never below 1e-4; Ux/Uz/p <= 1e-8, and dp / outlet flux
  change <= 1e-8 relative over the last 1000 iterations and versus the published fields.
- Status kept `max_iterations_reached` (OpenFOAM did not announce convergence). The evidence
  supports, but does not prove, a Uy-normalisation artefact.
- Fields are now exported at full resolution (1920 cells); the former stride-2 export is
  reproduced exactly.

## Mesh study (base 24×1×80 vs fine 48×1×160)

Stored in `data/simulations/cfd/mesh_study/B16_base_vs_fine.json`.
Relative |fine−base|/|base| on mid-gap Uz and inlet−outlet Δp was computed, but
**mesh independence remains `not_demonstrated`** because the fine Vg072/Vg755
runs (and Vg755 base) did not announce SIMPLE convergence.

## Reproduce demo

```powershell
# API + web (from repo root)
.\init-prometeo.bat
# or: pnpm dev:api  and  pnpm --filter frontend dev
# Open /compare, select a B16 trial, scroll to CFD Physics Lab
# Clicking a B16 point syncs the CFD case and vice versa
```

Re-run CFD (optional, Docker required):

```powershell
python tools/cfd/scripts/generate_and_run.py --run --mesh-study
```
