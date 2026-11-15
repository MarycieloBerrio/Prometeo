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
| CFD-B16-Vg072 | yes (endTime≤5000) | **yes** — `SIMPLE solution converged in 330 iterations` | numerically_checked | 1.35e-10 | mesh_ok | not_verified |
| CFD-B16-Vg083 | yes | **yes** — `SIMPLE solution converged in 619 iterations` | numerically_checked | 8.97e-12 | mesh_ok | not_verified |
| CFD-B16-Vg167 | yes (Time=5000s) | **no** — max_iterations_reached; final Uy initial residual > 1e-4 | solver_executed | 1.99e-11 | mesh_ok | not_verified |
| CFD-B16-Vg755 | yes (Time=5000s) | **no** — max_iterations_reached; final Uy initial residual > 1e-4 | solver_executed | 4.06e-11 | mesh_ok | not_verified |

UI screenshots (honest labels): `docs/assets/cfd-audit/`.

## Scientific limits (do not dilute)

- Not a reproduction of BASS-II combustion.
- Does not invent absolute pressure.
- Does not generate Vf, temperature, or O₂ fields.
- Does not claim 0g vs 1g from isothermal forced flow.
- Mesh independence documented per case (`not_demonstrated` unless a base/fine study reports otherwise).
- Field viewer shows a **scalar** sampled field (|U| or p); no streamlines fabricated from |U|.

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
