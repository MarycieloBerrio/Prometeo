# Science validation — Daniel (physics / comparability)

**Date:** 2026-11-14 (iteration 2)  
**Branches:** `feat/daniel-physics-validation` (PR #7, **merged**) · `feat/daniel-physics-validation-iter2` (follow-up)  
**PR #7:** https://github.com/MarycieloBerrio/Prometeo/pull/7  

Exclusive Daniel science note. Shared docs / curated data / other owners’ modules were not edited.

---

## 1. Physical problem

In microgravity, opposed-flow flame spread over thick PMMA rods is **non-monotonic** in
ventilation speed \(V_g\) (Link et al., *Sci. Rep.* 8:120 (2018), Fig. 6a): samples **B16**
(\(X_{O_2}=18.2\%\)) and **B19** (\(X_{O_2}=17.5\%\)).

API Δ = controlled experimental effect only when controls are **known and matched**.
Unknown ≠ equal. Same-`sample_id` condition points ≠ independent replicates.

---

## 2. Comparability semantics (engine)

| Level | Meaning | Deltas |
|---|---|---|
| `directly_comparable` | Controls documented & matched; varied factor actually changes; evidence-grade metrics | Allowed |
| `partially_comparable` | Unknown controls, empty/multi-factor isolation, same-sample series, soft mismatches | **Withheld** |
| `not_comparable` | Essential physical incompatibility | **Withheld** |

**DIRECT ≠ causal proof ≠ independent replication ≠ EvidenceTier.DIRECT.**

### Essential mismatches (not waivable via `varied`)

Fuel, geometry type, thermal regime (when known), **and flow direction**
(opposed / concurrent / quiescent). Cross-regime UI browsing of two sheets is fine; the
strict comparator stays `not_comparable`.

### Tolerance policy (iteration 2)

| Quantity | Match rule | Why |
|---|---|---|
| Flow speed, thickness, pressure | Relative `DEFAULT_REL_TOL=5%` via `Quantity.is_close` | Bookkeeping heuristic only |
| **Oxygen** | Absolute ≤ **0.3 percentage points** (`OXYGEN_ABS_TOL_PERCENT_POINTS`) | Link 2018 Fig. 7 states ±0.3% O₂ in μg. Relative 5% would falsely equate **18.2% vs 17.5%** (~3.85% rel., **0.7 pp** abs.) |

No invented instrument model beyond that published reporting band.

### Empty / multi-factor isolation

Declaring `flow_speed` or `oxygen` as varied when values match within the justified band →
**WARNING** (pair cannot stay DIRECT under a false effect claim).  
≥2 factors actually differing → **WARNING** (not single-factor isolation).

### Evidence deltas (`CompareTrials`)

Only **measured** or **derived (with method)** with **traceable** provenance.
Both-`SYNTHETIC` allowed for fixtures only. `EXTRACTED` / `UNAVAILABLE` never produce deltas.

### Flame-spread sign convention

`+x` = intended front advance. Caller orients the axis before `flame_spread_velocity[_fit]`.
Negative slopes are rejected (no silent `abs()`). **Handoff Juanfer:** orient FlameVision
samples; do not change the metrics API without a calibration contract.

---

## 3. Live engine matrix — B16 / B19 (iteration 2)

Sources: Link 2018 + ESM Table S1 (cm/s×10³ interpretation re-verified); curated JSON by Yulian
(not modified). Executed via `CompareTrials` on this branch.

| IDs | Varied | Controlled (documented) | Unknown / notes | Same sample? | Level | Issues (summary) | Deltas | Valid descriptive claim | Forbidden causal claim |
|---|---|---|---|---|---|---|---|---|---|
| B16-Vg755 vs B16-Vg167 | `flow_speed` | PMMA, cylinder Ø, thick, opposed, O₂ 18.2% | pressure both null; stepped series | **Yes (B16)** | **PARTIAL** | pressure unknown; same-sample; isolation invalid (pressure); thickness=diameter INFO | **withheld** | Recorded \(V_f\): 0.0678 vs 0.0762 mm/s; Fig. 6a narrative | “Controlled effect of ventilation alone”; independent replicates |
| B16-Vg167 vs B16-Vg072 | `flow_speed` | same | pressure; stepped series | **Yes (B16)** | **PARTIAL** | same family as above | **withheld** | \(V_f\): 0.0762 vs 0.0568 mm/s (low-flow branch) | Causal DOE Δ |
| B16-Vg755 vs B16-Vg072 | `flow_speed` | same | pressure; stepped series | **Yes (B16)** | **PARTIAL** | same family | **withheld** | Endpoints of curated B16 \(V_g\) span | Causal DOE Δ |
| B16-Vg167 vs B19-Vg167 | `oxygen` | PMMA, Ø, thick, opposed, \(V_g=1.67\) cm/s | pressure; different burn histories | **No** | **PARTIAL** | pressure unknown; isolation invalid (pressure); O₂ **does** differ beyond 0.3 pp | **withheld** | Association at matched \(V_g\): O₂ 18.2% vs 17.5%, \(V_f\) 0.0762 vs 0.0652 mm/s | Isolated O₂ effect with all else controlled |

**Descriptive non-monotonic ordering (B16 recorded values only):**  
\(V_f(1.67)>V_f(7.55)>V_f(0.72)\) → 0.0762 > 0.0678 > 0.0568 mm/s (Fig. 6a shape).

**No curated real pair is DIRECT** until pressure (or agreed N/A) is curated.

### Table S1 units

ESM dual header: left `Vf×10³ (cm/s)`, right `Vf×10³ (mm/s)`. Magnitudes match cm/s×10³ /
Table S2. Conversion in curated data: `Vf_mm/s = (Vf×10³)_cm/s × 0.01`. Residual PDF ambiguity
documented; Yulian data not altered.

---

## 4. Iteration 2 audit log

| Finding | Status |
|---|---|
| None/None pressure silent match | **Resolved in #7** |
| PARTIAL returning causal deltas | **Resolved in #7** |
| Relative 5% equating O₂ 18.2↔17.5 | **Confirmed risk → fixed** (absolute 0.3 pp) |
| `varied` waiving fuel/geometry/regime | **Fixed in #7** |
| `varied` waiving flow_direction | **Confirmed → fixed** (always essential) |
| Empty varied factor still DIRECT (INFO only) | **Confirmed → fixed** (WARNING) |
| Multi-factor described as single isolation | **Fixed** (WARNING) |
| EXTRACTED/UNAVAILABLE same-tag deltas | **Confirmed → fixed** |
| Negative \(v_f\) rejecting −x advance | **Documented convention**; no silent abs(); Juanfer handoff |
| Yulian observational test obsolete asserts | **Resolved by Yulian** (commit on #7 / PR #8 path); suite green on main+iter2 |

---

## 5. Jury demo (keep honest)

Show B16-Vg072 / Vg167 / Vg755 sheets + Fig. 6a. Compare Lab will show **PARTIAL** + withheld
deltas + warnings. Narrate recorded \(V_f\) and the paper; **do not** claim an engine causal Δ
or three independent burns.

---

## Integration handoff

### Yulian
- Observational test aligned (thanks). Dual-null pressure → PARTIAL is now expected.  
- For future DIRECT: curate pressure or schema N/A; diameter field migration still post-freeze.  
- O₂ equality uses ±0.3 pp, not 5% relative.

### Alejandro
- `Comparability.PARTIAL` pairs remain groupable (`!= NOT_COMPARABLE`).  
- `EvidenceTier.DIRECT` ≠ physical DIRECT.  
- Do not narrate withheld Compare deltas. Assistant tests on this branch: **PASS**.

### Marycielo
- Surface issues + `withheld_reason`; no causal Δ chart when withheld.  
- Mention same-sample / pressure-unknown / O₂ band in copy.

### Juanfer
- Orient +x along intended spread before calling metrics; negative slope = reject, not abs.  
- Luminous edge ≠ pyrolysis/temperature.

---

## Remaining jury limitations

- No real DIRECT curated pair (pressure unknown).  
- Condition points share thermal history.  
- Diameter stored in `thickness`.  
- PSI-25 ↔ Table S1 row audit incomplete.  
- 5% relative tol remains heuristic for non-O₂ quantities.
