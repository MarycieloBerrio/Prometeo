# CFD Physics Lab — scientific evidence brief (source for the slides)

Status date: 2026-11-16. Applies to `main@98ae6d2` plus two open, unmerged PRs:
**#24** `fix/cfd-visualization-integrity` (viewer, chart, wording, `geometry.diameter`) and
**#25** `fix/cfd-numerical-verification` (patch flux balance, iteration semantics, full-resolution
fields, Uy residual audit). Items marked **(PR #25)** are only true once #25 is merged.

Every number below comes from a repository file or from the primary source, and the file is named.

---

## 1. What NASA measured (experimental observation)

Source: Link, Huang, Fernandez-Pello, Olson, Ferkul, *The Effect of Gravity on Flame Spread over
PMMA Cylinders*, **Sci. Rep. 8, 120 (2018)**, DOI 10.1038/s41598-017-18398-4; data in
**Supplementary Table S1** (checked against the original PDF on 2026-11-16).

- BASS-II on the ISS: cast **black PMMA rods**, diameters 6.4 / 9.5 / 12.7 mm, **57.2 mm long,
  hemispherical ends**; opposed forced flow 0.4–8 cm/s; O₂ 16–21 % (volume fraction).
- Procedure (article, Methods): each rod was ignited at a relatively high opposed flow; the flow
  was then **reduced step by step** (B16: 7.6 → 0.7 cm/s), each step ≥ 1 min to reach
  quasi-steady spread. No spread below ~0.6 cm/s.
- Sample **B16**: d = 0.64 cm, O₂ = 18.2 %. Curated in `data/curated/trials.json`:

| Vg (cm/s) | Δt (s, Table S1) | Table S1 entry 10³·Vf (cm/s) | Vf (mm/s) | quality |
|---:|---:|---:|---:|---|
| 7.55 | 72 | 6.78 | 0.0678 | measured |
| 1.67 | 139 | 7.62 | 0.0762 | measured |
| 0.83 | 198 | 6.99 | 0.0699 | measured |
| 0.72 | 170 | 5.68 | 0.0568 | measured |

  Conversion: Table S1 tabulates 10³·Vf in cm/s, so 5.68 → Vf = 5.68×10⁻³ cm/s = 0.0568 mm/s.
  The PDF labels one column group "(mm/s)" but the other group and Table S2 use "(cm/s)"; only
  the cm/s reading is consistent with the article's statement that below 19 % O₂ spread is
  faster in microgravity than in 1 g. This was already noted in the curated record.

  > Δt check: Table S1 gives **198 s** (0.83 cm/s) and **139 s** (1.67 cm/s). A draft
  > table circulating in the team (169 s / 136 s) does not match the source; use 198 / 139.

- Sample B19 (O₂ 17.5 %): Table S1 has 4 points; 2 are curated (Vg 1.67 → 0.0652 mm/s,
  Vg 7.55 → 0.0469 mm/s).
- **These are condition points of one rod, in one burn**: not independent ignitions, no
  replicates, no uncertainty bars. The authors report the trend "first increases, and then
  decreases" (Fig. 6a); for B16 that shape rests on one value per flow speed.

## 2. What OpenFOAM computes (numerical simulation)

Source: `tools/cfd/README.md`, `data/simulations/cfd/manifests/*.json`.

- OpenFOAM 11, `foamRun` + `incompressibleFluid`, steady **SIMPLE**, laminar, isothermal,
  incompressible, **non-reactive** air (ν = 1.5×10⁻⁵ m²/s, ~300 K, 1 atm).
- Solved fields: velocity **U** [m/s] and **kinematic pressure p = P/ρ** [m²/s²], relative,
  with p = 0 at the outlet.
- Four cases, one per B16 Vg: CFD-B16-Vg072 / Vg083 / Vg167 / Vg755.

## 3. Equations, units and boundary conditions

Steady incompressible Navier–Stokes (what the solver discretises):

- continuity: ∇·**U** = 0
- momentum: (**U**·∇)**U** = −∇p + ν∇²**U**, with p = P/ρ (kinematic, m²/s²)

| Boundary | U | p |
|---|---|---|
| inlet (z = 0) | fixed uniform (0, 0, Vg) | zeroGradient |
| outlet (z = 120 mm) | zeroGradient | 0 (reference) |
| rod surface (r = 3.2 mm) | no-slip | zeroGradient |
| duct wall (r = 38 mm) | no-slip | zeroGradient |
| front/back | wedge (axisymmetry) | wedge |

Derived numbers (estimates from the geometry, for context): hydraulic diameter
D_h = 2(R_o − R_i) = 69.6 mm; Re_Dh = Vg·D_h/ν = 33 (0.72 cm/s) to 350 (7.55 cm/s), all laminar.

The flow-side quantity in the literature (quoted, **not computed** by Prometeo): Link et al.
characterise the chemical regime with a convective Damköhler number written in their Eq. 1 as
**Da = t_chem / t_flow**. Note this ratio convention (chemical time over flow time).
Prometeo does not evaluate Da or state how it varies with Vg.

## 4. Geometry and model simplifications (must stay visible)

| Experiment (BASS-II) | Model |
|---|---|
| square duct 76 × 76 mm | circular duct R_o = 38 mm (circularised) |
| rod 6.4 mm, 57.2 mm long, hemispherical ends | infinite rod wall R_i = 3.2 mm along the whole 120 mm domain |
| 3-D | 2-D axisymmetric wedge, 5° |
| flame, pyrolysis, radiation, buoyancy | none (isothermal, non-reactive, no gravity) |

Mesh: 24 (radial) × 1 × 80 (axial) = 1920 cells, checkMesh OK.

## 5. Results available

| Case | Convergence (published) | Final SIMPLE iteration | Final initial residuals Ux / Uy / Uz / p | Patch volume-flux balance **(PR #25)** | Δp inlet−outlet, mean kinematic (m²/s²) **(PR #25)** |
|---|---|---:|---|---|---:|
| Vg072 | **converged** (OpenFOAM: "SIMPLE solution converged in 330 iterations") | 330 | 2.0e-8 / 9.9e-5 / 6.6e-9 / 2.5e-9 | 4.4e-9, verified | 1.61e-4 |
| Vg083 | **converged** (619 iterations) | 619 | 6.7e-10 / 9.9e-5 / 1.8e-10 / 1.1e-9 | 3.9e-9, verified | 1.90e-4 |
| Vg167 | **max_iterations_reached** (not converged) | 5000 | 2.1e-9 / **4.1e-4** / 2.7e-10 / 2.5e-9 | 9.6e-9, verified | 4.37e-4 |
| Vg755 | **max_iterations_reached** (not converged) | 5000 | 2.9e-15 / **6.2e-4** / 1.3e-15 / 5.8e-9 | 2.1e-9, verified | 3.20e-3 |

- "Time = 5000" in the log is the **SIMPLE iteration counter**, not 5000 seconds **(PR #25 wording)**.
- Patch balance = |φ_in + φ_out| / |φ_in|. φ is a **volumetric** flux (m³/s) through the 5° wedge
  sector, not a mass flow. Tolerance 1e-6; values are at the 9-digit output-precision floor.
  The inlet flux equals Vg × patch area exactly.
- **Uy audit (PR #25,** `data/simulations/cfd/verification/2026-11-16-uy-audit/`**):**
  - OpenFOAM 11 applies the U criterion to the **largest component residual**. In every case
    that component is **Uy**, the wedge-tangential component, physically ~1e-15·Vg.
  - Re-running Vg167/Vg755 to 30 000 iterations with the unchanged criterion: Uy stays between
    2e-4 and 1e-3. Ux/Uz/p stay ≤ 1e-8. Δp and outlet flux change by ≤ 1e-8 relative, and match
    the published fields.
  - OpenFOAM never announced convergence, so the status **stays not converged**. The evidence
    supports, but does not prove, a residual-normalisation artefact.
  - Per-component keys (`Ux`, `Uz`) are silently ignored by OpenFOAM 11; a test run
    "converged" on p alone. Do not use them.
- Velocity structure (field files): peak |U| ≈ 1.56·Vg (0.72–1.67 cm/s) and 1.39·Vg (7.55 cm/s).
  This follows from no-slip on both walls plus volume conservation; at 7.55 cm/s the profile is
  still developing within 120 mm (higher Re).
- Field export: 960 of 1920 cells on main; **all 1920 cells (PR #25)**, reproducing every
  previous sample exactly. The viewer **(PR #24)** shows the available resolution and never
  interpolates.
- **Mesh independence: not demonstrated.** The base vs fine comparison exists but the fine
  meshes did not converge.

## 6. What the literature interprets (literature-based, not demonstrated by our CFD)

From Link et al. 2018, Discussion (verified in the article text):

- **Thermal regime** (low opposed flow): a faster flow moves the flame closer to the surface,
  raises heat transfer to the solid ahead, and Vf increases.
- **Chemical regime** (larger flow or lower O₂): the flow cools the gas-phase reaction, the flame
  weakens, spread slows, and eventually the flame blows off. Characterised by Da = t_chem / t_flow
  as written (Eq. 1).
- **Very low flow**:
  - surface radiative losses and slow oxygen transport lead to very slow spread and extinction;
    some authors call this "radiation extinction" or the "oxygen-transport limited" regime;
  - the authors say better diagnostics are needed to separate the two contributions;
  - blow-off at high flow was **not observed** on the ISS (limited fan power).

Our isothermal, non-reactive CFD contains none of these mechanisms (no chemistry, no radiation,
no energy equation). It can show the forced-flow velocity and pressure field at each Vg, nothing
about which regime operates.

## 7. What the Research Assistant adds

- Hybrid retrieval (full-text + pgvector) over the NASA PSI knowledge base: 24 investigations and
  4 509 chunks on the reference machine, with the curated trials.
- Answers carry an evidence tier (`direct` / `partial` / `insufficient`), cite the source passage
  with page and DOI, and can open the original PDF at that page.
- Numbers come from the deterministic Evidence Engine, never from the language model.
- Example (recorded 2026-11-15): for the B16 non-monotonic question it returned tier **partial**
  and stated that the four points are one sample with no uncertainty. It also retrieved the
  BASS-II Summary Report (p. 56), whose averaged data show Vf **increasing** with opposed flow.
  That is consistent only with the rising part of B16 and is worth showing as a nuance.

## 8. Limitations (say them on the slide)

- CFD is non-reactive, isothermal, laminar, 2-D axisymmetric, without gravity. It has no flame,
  temperature, pyrolysis, O₂ transport or radiation, and **cannot predict Vf** or extinction.
- Geometry is simplified: circular duct, infinite rod, no rod tips, uniform inlet profile.
- Two of the four cases are formally **not converged** (Uy criterion); see the audit above.
- **No mesh independence.**
- B16 Vf points are a single-sample, single-burn sequence with no replicates or uncertainty.
  Vg is confounded with time and position along the rod.
- Cabin pressure is not recorded for these rows; kinematic p is relative and is **not** absolute
  pressure.
- 0 g vs 1 g differences cannot be shown with an isothermal forced-flow model.

## 9. Claims we can defend in front of the jury

- "We measured nothing ourselves: the Vf values are NASA BASS-II data (Link et al. 2018,
  Table S1), traceable to the table entry, with units converted explicitly."
- "In B16, Vf is non-monotonic in Vg: it rises from 0.72 to 1.67 cm/s and is lower at
  7.55 cm/s. This is an apparent maximum observed once in one sample."
- "Our OpenFOAM model gives the cold forced-flow field around the rod at the same Vg values.
  The gas accelerates to ~1.4–1.6×Vg in the annulus because of no-slip and volume
  conservation."
- "The flux entering equals the flux leaving to better than 1e-8 in all four solutions." **(PR #25)**
- "Two cases converged by OpenFOAM's own criterion. Two did not, and we show them labelled as
  such. Our audit shows the blocking residual is the analytically null tangential component."
  **(PR #25)**
- "The literature attributes the rise to a thermal regime and the fall to a chemical regime
  (Link et al. 2018). Our CFD neither proves nor disproves that."

## 10. Claims we must NOT make

- That the CFD simulates the flame, predicts Vf, temperature, pyrolysis, extinction or blow-off.
- That 1.67 cm/s is a statistically demonstrated peak or optimum, or that Vg alone causes the
  change.
- That Vg167/Vg755 are converged, or that the solution is mesh-independent.
- That p is cabin or absolute pressure.
- That the model shows 0 g vs 1 g differences, or anything about lunar or Martian gravity.
- That Da rises or falls with Vg in our model (we do not compute it), or any Da formula other
  than the one in the source.
- Any "% safe" or "% confidence", or that a material is safe because no evidence was found.
- Error bars or uncertainty for the B16 points.

## Evidence status table

| Claim | Status | Evidence |
|---|---|---|
| Experimental Vf (B16, 4 points) | MEASURED | Link et al. 2018, Table S1; `data/curated/trials.json` |
| Velocity field | COMPUTED | OpenFOAM 11, `data/simulations/cfd/fields/*.json` |
| Kinematic pressure (relative, p = 0 at outlet) | COMPUTED | OpenFOAM 11, same files |
| Convergence | Per case: Vg072/Vg083 CONVERGED (solver-announced); Vg167/Vg755 NOT CONVERGED (max iterations) | `log.foamRun`, manifests, `verification/2026-11-16-uy-audit/` |
| Flux balance | VERIFIED ≤ 1e-8 **(PR #25)**; NOT VERIFIED on current main | φ inlet/outlet, `flux_published.json` |
| Mesh independence | NOT DEMONSTRATED | `mesh_study/B16_base_vs_fine.json` (fine meshes not converged) |
| CFD flame propagation | NOT IMPLEMENTED | Outside the current model |
| Thermal and chemical mechanisms | LITERATURE-BASED | Link et al. 2018, Discussion |
| Apparent Vf maximum at intermediate Vg (B16) | OBSERVED once, not statistically demonstrated | Table S1, one sample, no replicates |
| Uy residual as cause of non-convergence | SUPPORTED, NOT PROVEN | 30 000-iteration reruns **(PR #25)** |
