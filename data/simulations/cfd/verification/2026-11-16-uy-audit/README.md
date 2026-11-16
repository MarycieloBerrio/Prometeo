# Verification run 2026-11-16-uy-audit (pre-registered)

Written **before** any run. The published results in `../../manifests/` and `../../fields/` are
not modified by these experiments; their SHA-256 at the start are in `published_sha256_before.txt`.

## Questions

1. Is the `max_iterations_reached` status of CFD-B16-Vg167 / Vg755 caused by the residual of
   `Uy` (tangential component, analytically zero in the axisymmetric wedge)?
2. Does OpenFOAM 11 honour per-component `residualControl` keys (`Ux`, `Uz`)?
3. Do the published solutions conserve volume flux between inlet and outlet patches?

## Experiments

| id | cases | change vs published runs |
|---|---|---|
| `flux_published` | all 4 | none — post-processing of copies of the published final iterations |
| `component_keys` | Vg755 | `residualControl { Ux 1e-6; Uz 1e-6; p 1e-6; }`, endTime 5000 |
| `extended_budget` | all 4 (072/083 = controls) | same `residualControl { p 1e-4; U 1e-4; }`, endTime 30000, monitoring function objects |

Mesh, boundary conditions, schemes, linear solvers and relaxation are copied unchanged.

## Acceptance criteria (fixed before running)

- **Patch flux balance verified** if the inlet flux is negative, the outlet flux positive and
  |φ_in + φ_out| / |φ_in| ≤ 1e-6 (double-precision fluxes, solver tolerance 1e-8, so a
  balance far below 1e-6 is expected for a converged incompressible solution).
- **A case may be proposed as converged** only if, in a rerun with the **unchanged**
  `residualControl` (U includes Uy), OpenFOAM itself announces `SIMPLE solution converged`.
- **External stationarity evidence** (reported, never used alone to relabel a case): over the
  final 1000 iterations Δp and outlet flux change by ≤ 1e-6 relative, Ux/Uz/p initial residuals
  ≤ 1e-6, flux balance ≤ 1e-6, and max|Uy|/Vg ≤ 1e-9.
- The published convergence statuses are **not** changed by this run; any change would be a
  separate, reviewed decision that republishes the new run's fields with their own evidence.

---

## Results (appended after the runs, 2026-11-16 ~04:35 UTC)

OpenFOAM 11 (`openfoam/openfoam11-paraview510`), same mesh (24x1x80), BCs, schemes and solvers.

### Q2 — per-component `residualControl` keys are NOT honoured (OpenFOAM 11)

Source (`singleRegionConvergenceControl.C`, `convergenceControlTemplates.C`): residual-control
keys are matched against **field names**; for a vector field the residual compared is
`cmptMax(initialResidual)` — the largest of Ux, Uy, Uz. Keys `Ux`/`Uz` match no field and are
accepted silently. Run `component_keys` confirms it: OpenFOAM announced
`SIMPLE solution converged in 108 iterations` while Ux = 1.80e-5 and Uz = 1.95e-6 were above
the requested 1e-6 (and Uy = 4.6e-3): convergence was decided by `p` alone (9.9e-7).
**Do not use `{Ux 1e-6; Uz 1e-6; p 1e-6;}`.**

### Q1 — the U criterion is dominated by Uy (wedge tangential component)

| run (`extended_budget`, unchanged residualControl U 1e-4, p 1e-4) | outcome | final iteration | final initial residuals Ux / Uy / Uz / p | max abs(Uy) / Vg |
|---|---|---:|---|---:|
| Vg072 (control) | converged (reproduces published 330 it.) | 330 | 2.0e-8 / **9.94e-5** / 6.6e-9 / 1.2e-8 | 1.1e-15 |
| Vg083 (control) | converged (reproduces published 619 it.) | 619 | 6.7e-10 / **9.89e-5** / 1.8e-10 / 1.1e-8 | 1.1e-15 |
| Vg167 | max_iterations_reached | 30000 | 1.4e-9 / **2.90e-4** / 1.9e-10 / 4.5e-9 | 1.0e-15 |
| Vg755 | max_iterations_reached | 30000 | 3.4e-15 / **4.80e-4** / 1.3e-15 / 5.8e-9 | 1.2e-15 |

In every case the component that decides the U criterion is Uy; even the two "converged"
controls pass with Uy just under 1e-4. Between iterations 5000 and 30000 the Uy residual of
Vg167/Vg755 oscillates between 2.0e-4 and 9.8e-4 and never reaches 1e-4, while the physical Uy
magnitude is ~1e-15 Vg (round-off). Over the final 1000 iterations of Vg167 / Vg755:

| | Vg167 | Vg755 |
|---|---:|---:|
| max relative change of dp (inlet minus outlet mean kinematic p) | 2.3e-9 | 0 (at 9-digit output) |
| max relative change of outlet flux | 9.6e-9 | 0 |
| max Ux / Uz / p initial residual | 2.4e-9 / 3.0e-10 / 1.1e-8 | 3.4e-15 / 1.3e-15 / 5.8e-9 |
| dp at iteration 5000 (published run) vs 30000, relative | 2.3e-9 | 0 |

These meet every pre-registered *external stationarity* threshold. Per the pre-registered rule
they are **evidence, not a relabel**: OpenFOAM never announced convergence under the unchanged
criterion, so the published status stays `max_iterations_reached`. The data support the
hypothesis that the non-convergence is an artefact of the normalised residual of an
analytically null component, but proving it would need a criterion that OpenFOAM 11 does not
offer per component (e.g. a formulation without the tangential component, or an
absolute-residual criterion) — left as follow-up.

(The 1000-iteration window statistics for the controls are not meaningful: they stopped at
330/619 iterations, so their window includes start-up.)

### Q3 — patch volume-flux balance of the published solutions

`flux_published.json`: inlet flux < 0 < outlet flux for all four; abs(phi_in + phi_out)/abs(phi_in) =
4.4e-9 (Vg072), 3.9e-9 (Vg083), 9.6e-9 (Vg167), 2.1e-9 (Vg755) — at the 9-digit output
precision floor, <= 1e-6, so **verified**. abs(phi_in) / (Vg * A_analytic) = 0.99873 in every case,
equal to sin(theta)/theta for the planar faces of the 5-degree wedge (patch area 6.248e-5 m2): the
inlet carries exactly Vg through the meshed area. phi is a volumetric (kinematic) flux in m3/s
through the wedge sector, not a mass flow.

### Files

- `flux_published.json`, `refresh_report.json` (hash before/after of every refreshed manifest
  and field; statuses unchanged; the full-resolution export reproduces every previous sample).
- `component_keys/`, `extended_budget/`: `*_summary.json` and per-iteration `*_history.csv`
  (iterations 1-100, every 10th, and the final 1000 in full for the 30000-iteration runs; the
  SHA-256 of each full history is in `*_history_full.sha256`).
- Mesh independence: **not demonstrated** (no new mesh study in this run).
