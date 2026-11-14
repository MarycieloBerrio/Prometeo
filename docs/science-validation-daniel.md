# Science validation — Daniel (physics / comparability)

**Branch:** `feat/daniel-physics-validation`  
**Date:** 2026-11-14  
**Scope:** Physics Validator, metrics, CompareTrials causal-delta policy, EvidenceRank notes.

This document is the exclusive science handoff for Daniel. Shared docs (`docs/science.md`,
`AGENTS.md`) were not modified (frozen during parallel PRs).

---

## 1. Physical problem

In microgravity, flame spread over solids is often **non-monotonic** in forced ventilation:
increasing opposed flow can first strengthen then weaken the flame (thermal vs chemical
regimes). A numeric Δ of flame-spread rate is only a **controlled effect** when every other
relevant factor is known and matched. **Unknown ≠ equal.** Association across mixed
conditions is not causation.

---

## 2. Compatibility decisions implemented

| Rule | Level | Deltas |
|---|---|---|
| Categorical mismatch (fuel, geometry, thermal regime, flow direction) when controlled | `not_comparable` | withheld |
| Synthetic ↔ real mix | `not_comparable` | withheld |
| Controlled numeric mismatch beyond 5 % rel. tol., or unknown on one/both sides | `partially_comparable` | withheld |
| Claimed single-factor isolation but other controlled essentials also differ/unknown | `partially_comparable` (+ isolation warning) | withheld |
| All controlled factors documented and matched; only `varied` differs | `directly_comparable` | allowed (commensurable qualities/units only) |

**Relative tolerance (5 %):** bookkeeping heuristic for “same condition” on documented
quantities (`Quantity.is_close` uses `max(|a|,|b|)` as scale). It is **not** universal
physical equivalence. Near zero, two exact zeros match; a tiny vs non-tiny value fails
relative to the larger magnitude.

**Flow regimes:** `opposed`, `concurrent`, and `quiescent` are distinct. They must not be
confused with O₂ mole fraction or with ventilation *speed*. Speed can be varied only when
direction is known and matched (or explicitly varied).

---

## 3. Evidence matrix (primary sources)

Sources read (open abstract/full text / NTRS landing + TM summary; Supplementary Table S1
via Springer ESM listing):

1. Link et al., *Sci. Rep.* **8**:120 (2018) — https://www.nature.com/articles/s41598-017-18398-4  
   ESM Table S1: https://media.springernature.com/original/springer-static/esm/art%3A10.1038%2Fs41598-017-18398-4/MediaObjects/41598_2017_18398_MOESM1_ESM.pdf
2. Olson et al., NASA/TM-20210011385 — https://ntrs.nasa.gov/citations/20210011385
3. Olson et al., concurrent PMMA rods (2015) — https://ntrs.nasa.gov/citations/20150008961
4. (P2) Confinement / np-MR context 2024 — https://link.springer.com/article/10.1007/s12217-024-10106-y (limits noted; no new curated tables)

| Physical question | Response variable | Controlled variables | Source (page/fig/table) | Allowed comparison | Confusion risks | Trial JSON field | Evidence quality |
|---|---|---|---|---|---|---|---|
| How does opposed-flow speed change flame spread in μg? | Flame spread rate \(V_f\) | Fuel (PMMA), rod diameter, \(X_{O_2}\), flow **direction=opposed**, pressure (often unreported) | Link 2018 Fig. 6a; ESM Table S1 (samples B16, B19) | Same sample / same \(X_{O_2}\) / same diameter / opposed only; vary `flow_speed` | Stepped-flow points on one rod ≠ independent replicates; Fig. 4 photo sequences | `ventilation.speed`, `results[flame_spread_rate]` | measured (paper); pressure often **unknown** → PARTIAL until curated |
| Non-monotonic \(V_f(V_g)\) in μg vs 1g | \(V_f\) vs \(V_g\) | Gravity level (μg vs 1g), \(X_{O_2}\), diameter | Link 2018 Fig. 6a vs 6b | Do **not** pool μg and 1g as one series | Buoyancy ~30 cm/s masks low-\(V_g\) branch on Earth | (no gravity field in schema — **AÚN NO VERIFICADO** as Trial attribute) | interpretive |
| Effect of \(X_{O_2}\) at matched flow | \(V_f\) | PMMA, diameter, \(V_g\), opposed | Link 2018 Fig. 4, 6a, 8; Table S1 B16 vs B19 | Vary `oxygen` only when \(V_g\) matched | Mixing B16 (18.2%) with B19 (17.5%) at different \(V_g\) | `oxygen` | measured |
| LOC / quenching at low flow | extinction / spread presence | \(X_{O_2}\), \(V_g\), diameter | Link 2018 text (~0.6 cm/s quench); Fig. 8 | Binary outcomes need explicit phenomenon tags | “No spread” ≠ safe material | `phenomena`, notes | partial / contextual |
| Concurrent-flow flammability of PMMA rods | blowoff / quench limits | O₂, axial flow, rod geometry | NTRS 20150008961 (BASS concurrent) | **Not** directly comparable to opposed Link-2018 series | Concurrent ≠ opposed | `ventilation.direction` | separate series |
| Heat release from O₂ consumption | \(\dot Q \approx 13.1\,\mathrm{kJ/g_{O_2}}\cdot\Delta m/\Delta t\) | Calorimetry assumptions of TM | NASA/TM-20210011385 abstract/body | Only when Δm_O₂ and Δt measured | Constant is procedure-specific | metric `heat_release_rate_from_o2` | derived (method required) |
| PSI-25 individual trial ↔ Table S1 row | — | sample id, \(V_g\), \(X_{O_2}\) | PSI-25 repo + Table S1 | Only after row-level provenance verified | Paper membership ≠ pairwise comparable | `id`, `sample_id`, provenance | **AÚN NO VERIFICADOS** without PSI file↔row audit |

### Candidate comparable pairs (no invented IDs/values)

From Link et al. 2018 / Table S1 narrative (also curated by Yulian when present):

| Pair intent | Candidate IDs (if curated) | Status |
|---|---|---|
| Same PMMA rod B16, same \(X_{O_2}\approx 18.2\%\), opposed, different \(V_g\) (e.g. 7.55 vs 1.67 cm/s) | `BASS-II-B16-Vg755` vs `BASS-II-B16-Vg167` | Scientifically the right isolation **if** pressure/other controls documented. With `pressure: null` on both → engine now returns **PARTIAL** (unknown controlled ≠ match). |
| Matched \(V_g\), B16 vs B19 (O₂ 18.2% vs 17.5%) | `BASS-II-B16-Vg167` vs `BASS-II-B19-Vg167` | Oxygen-variation candidate; still PARTIAL while pressure unknown. |
| PSI-25 raw run ↔ Table S1 cell | — | **AÚN NO VERIFICADOS** — need PSI file name, sample clock, and unit cross-check; do not invent. |

Thin-film BASS-II note (100 µm) vs thick rods: **not comparable** (geometry / thermal regime).

---

## 4. Flow-regime interpretation guide

1. **Opposed:** oxidizer velocity opposite to spread; Link-2018 non-monotonic \(V_f(V_g)\) applies here.  
2. **Concurrent:** co-flow; blowoff/quench maps differ (20150008961). Never subtract opposed − concurrent as a “ventilation effect.”  
3. **Quiescent:** no forced flow; diffusion-dominated; not “speed = 0 opposed” without evidence.  
4. **Do not assume “more wind ⇒ more fire.”** Low-\(V_g\) thermal branch can rise with flow; high-\(V_g\) chemical branch falls toward blowoff; radiation/O₂-transport extinction appears at very low flow in μg.

---

## 5. FlameVision measurement (handoff to Juanfer)

| Measurable in video | Not measurable from luminous video alone |
|---|---|
| Luminous leading-edge position vs time (pixels → mm with calibration) | Gas-phase reaction-zone location |
| Apparent luminous spread rate (unvalidated until reference check) | Peak temperature / HRR |
| Saturation / tracking rejection signals | Pyrolysis-front recession inside the solid |

Paper method (Link 2018): flame spread from **flame leading edge** on high-res stills (~1 s), linear \(x(t)\). That is closer to **luminous edge** than to a pyrolysis isotherm. Thermocouple/surface pyrolysis fronts require separate diagnostics. Keep `feature = luminous_leading_edge` and `unvalidated` until compared to a published \(V_f\).

---

## 6. P2 — Confinement (2024)

Article https://link.springer.com/article/10.1007/s12217-024-10106-y discusses microgravity flame behavior with confinement / np-MR-relevant geometry. **No new persistent tables** added. Risk: duct confinement and sample proximity change O₂ supply and heat loss — another reason not to pool BASS duct data with open or differently confined setups without an explicit confinement factor (schema currently has none).

---

## 7. EvidenceRank design note (Alejandro)

`overall_tier` still requires ≥2 non-insufficient assessments. That is correct for **comparative** causal questions. For single-trial descriptive Q&A, a new optional mode (e.g. `overall_tier(..., mode="descriptive")` or a separate helper) should be coordinated — **no public contract change in this PR**. Never emit "% confidence".

### Tier semantics for the assistant

| Tier | Meaning | Must not claim |
|---|---|---|
| `direct` | Usable trials are high relevance + high quality **and** coverage rule passed | Universal safety / certification |
| `partial` | Usable but weaker quality or mixed | Isolated causal Δ when Physics Validator is PARTIAL |
| `insufficient` | Too few usable trials / synthetic / untraceable | “No evidence ⇒ safe” |

---

## Integration handoff

### Yulian (data)

**Mandatory fields for DIRECT flow-speed comparisons:**  
`fuel.material`, `geometry.type`, `geometry.thickness` (or documented diameter policy), `geometry.thermal_regime` ≠ unknown, `oxygen`, `ventilation.speed`, `ventilation.direction` ≠ unknown, `pressure` (or an agreed future “not_applicable” — **not** invented here).  

**Unknown representation:** omit / `null` — **never 0**. Engine treats dual-null controlled vars as WARNING → PARTIAL.

Observational test `tests/data/test_bass2_table_s1_semantics.py::test_compare_behavior_observed_for_handoff_to_daniel` asserted pre-fix behaviour (dual-null pressure silent; deltas on PARTIAL). **Expect FAIL after this PR** — please update the observational assertions to PARTIAL + empty deltas + pressure WARNING.

### Alejandro (assistant / RAG)

- DIRECT/PARTIAL/INSUFFICIENT as above; no causal language when Compare/Physics Validator would withhold deltas.  
- Dual-unknown O₂ + different speeds ≠ “effect of ventilation.”  
- Recommend descriptive single-trial path without changing frozen HTTP in this PR.

### Marycielo (UI)

- Show all `compatibility.issues` messages (blocking vs warning).  
- `withheld_reason` non-null ⇒ **do not chart causal Δ**; still show each trial’s own values.  
- PARTIAL copy (engine): *“Trials are only partially comparable… Causal deltas are withheld…”*  
- Never label `SYN-*` as NASA results.

### Juanfer (FlameVision)

- Track luminous leading edge; do not claim pyrolysis front or temperature.  
- Duplicate timestamps must not produce a velocity (metrics now raise).  
- Validate against Table S1 / published \(V_f\) before flipping validation status.

---

## Remaining risks

- Schema has no gravity / confinement / diameter-vs-thickness distinction (Yulian notes diameter in `thickness`).  
- PSI-25 ↔ Table S1 row linkage still incomplete.  
- 5 % tolerance remains heuristic.  
- Stepped-flow condition points share thermal history — even DIRECT arithmetic Δ is not a fully independent DOE contrast.
