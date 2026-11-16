# Prometeo CFD Physics Lab (OpenFOAM 11)

Reproducible **axial** laminar isothermal incompressible **non-reactive** flow around a PMMA rod,
linked to BASS-II B16 opposed-flow condition points (Link et al. 2018).

This is a **numerical_simulation**, not an `experimental_observation`. It does **not** predict
flame spread rate, temperature, O₂ consumption, or 0g vs 1g differences.

## Solver

| Item | Value |
|---|---|
| Image | `openfoam/openfoam11-paraview510` |
| Application | `foamRun` + `incompressibleFluid` (SIMPLE, laminar, steady) |
| Equations | Continuity + momentum (velocity + kinematic pressure) |
| Fluid | Air, ν = 1.5×10⁻⁵ m²/s (isothermal ~300 K hypothesis) |

## Geometry (simplified vs NASA)

Reference: Link et al., *Sci. Rep.* 8:120 (2018) — 6.4 mm rod, 57.2 mm length, rounded tips,
76×76 mm duct, opposed flow, microgravity, B16 O₂ = 18.2% (scenario identifier only).

**MVP model differences (explicit):**

- 2D axisymmetric **wedge** (5°) annular duct.
- Square 76×76 mm duct **circularised** to outer radius 38 mm.
- Rod as continuous cylindrical wall (finite length / hemispherical tips **not** resolved).
- Axial flow along the rod — **not** cross-flow around a cylinder.

## Cases (published Vg)

| Case | Trial ID | Vg |
|---|---|---|
| CFD-B16-Vg072 | BASS-II-B16-Vg072 | 0.72 cm/s |
| CFD-B16-Vg083 | BASS-II-B16-Vg083 | 0.83 cm/s |
| CFD-B16-Vg167 | BASS-II-B16-Vg167 | 1.67 cm/s |
| CFD-B16-Vg755 | BASS-II-B16-Vg755 | 7.55 cm/s |

## Windows + Docker

Requirements: Docker Desktop with Linux containers.

```powershell
cd <repo-root>
python tools/cfd/scripts/generate_and_run.py --run
```

Environment detection: if Docker is unavailable, the script writes manifests with
`validation_status=pending_execution` and **does not invent fields**.

Outputs:

- Case trees under `tools/cfd/openfoam/cases/` (gitignored runtime mesh/time dirs).
- Manifests: `data/simulations/cfd/manifests/`
- Field samples: `data/simulations/cfd/fields/` — every mesh cell (1920), with mesh dimensions and cell order in each file

## WSL2

```bash
# with OpenFOAM 11 sourced, or via the same Docker image
python3 tools/cfd/scripts/generate_and_run.py --run
```

## Convergence classification (important)

| Outcome | Meaning |
|---|---|
| `converged` | Log contains `SIMPLE solution converged in N iterations` |
| `max_iterations_reached` | Process exited 0 but reached `endTime` **without** that announcement |
| `solver_failed` | Non-zero foamRun / blockMesh exit |
| `not_run` | Solver not executed |

Container stdout `DONE` is **never** treated as convergence.

`endTime` is an iteration budget for steady SIMPLE (deltaT = 1 pseudo-time: "Time = 5000" means iteration 5000, not seconds). It is 5000 iterations (raised from 400 to give Uy residual time to meet
`residualControl` 1e-4). Residual thresholds themselves are unchanged.

## Validation notes

- Residuals and SIMPLE continuity `global` are parsed from real `log.foamRun` output.
- Patch flux balance comes from the packaged OpenFOAM 11 function `patchFlowRate(patch=inlet|outlet)` (sum of `phi`, a volumetric flux through the 5-degree wedge sector), verified when abs(phi_in + phi_out)/abs(phi_in) <= 1e-6 — distinct
  from the SIMPLE continuity `global` residual.
- `checkMesh` metrics are stored under `mesh_quality` in each manifesto.
- Mesh study (optional): `python tools/cfd/scripts/generate_and_run.py --run --mesh-study`
  compares base `(24,1,80)` vs fine `(48,1,160)` for Vg072 and Vg755.
- Absolute B16 cabin pressure is **not invented**.

## Numerical verification (`verify_numerics.py`)

```powershell
python tools/cfd/scripts/verify_numerics.py --run-id <id> [--only flux_published component_keys extended_budget]
python tools/cfd/scripts/reclassify_manifests.py --run-id <id>   # refresh wording, flux and full fields; statuses unchanged
```

Runs on copies under `tools/cfd/openfoam/verification_runs/` (gitignored); results and
pre-registered criteria in `data/simulations/cfd/verification/<id>/`. OpenFOAM 11 applies the
`U` residual criterion to the largest component (Uy here) and silently ignores per-component
keys such as `Ux`/`Uz` — never use them to "fix" convergence.
