# Science validation — Daniel (physics / comparability)

**Date:** 2026-11-14 (addendum)  
**Branch:** `feat/daniel-physics-validation`  
**PR:** https://github.com/MarycieloBerrio/Prometeo/pull/7  

Exclusive Daniel science note. Shared docs were not modified.

---

## 1. Physical problem

In microgravity, opposed-flow flame spread over thick PMMA rods is **non-monotonic** in
ventilation speed \(V_g\): \(V_f\) can rise then fall as opposed flow increases (thermal vs
chemical regimes). Link et al., *Sci. Rep.* 8:120 (2018), Fig. 6a demonstrates this for
ISS/BASS-II samples **B16** (\(X_{O_2}=18.2\%\)) and **B19** (\(X_{O_2}=17.5\%\)).

A numeric API Δ is a **controlled experimental effect** only when controlled factors are
**known and matched**. Unknown ≠ equal. Condition points from one stepped burn are **not**
independent replicates.

---

## 2. Comparability semantics (engine)

| Level | Meaning | Deltas |
|---|---|---|
| `directly_comparable` | Controlled factors documented & matched; explicit varied factor; commensurate measurements | Allowed (same quality class; convertible units) |
| `partially_comparable` | Unknown controlled vars, same-sample stepped series, failed isolation, or non-blocking mismatches | **Withheld** + `withheld_reason` |
| `not_comparable` | Essential physical incompatibility | **Withheld** |

**DIRECT ≠ causal proof ≠ independent replication.** It only means the validator did not find
blocking/partial issues under the declared `varied` set.

**Essential mismatches are not waivable** by listing them in `varied`: fuel, geometry type,
thermal regime (when known). Flow direction remains isolable when explicitly varied.

**Flow regimes:** `opposed` ≠ `concurrent` ≠ `quiescent` (independent of O₂ and of speed).

**5% relative tolerance:** bookkeeping heuristic via `Quantity.is_close` (`max(|a|,|b|)` scale);
not universal physical equivalence.

### Comparability vs EvidenceTier (Alejandro)

| Concept | Owner | Meaning |
|---|---|---|
| `Comparability.DIRECT` | Physics Validator / Compare | Pairwise physical condition match |
| `EvidenceTier.DIRECT` | EvidenceRank / Assistant | Relevance + quality + coverage (≥2 usable trials) |

They are **not equivalent**. Assistant `_comparable()` treats anything except
`NOT_COMPARABLE` as groupable, so **PARTIAL** B16 pairs still form groups while Compare
**withholds deltas**. No assistant code changed in this PR.

---

## 3. B16 / B19 compatibility matrix (curated records)

Primary sources verified this session:

- Link et al. 2018 article: https://www.nature.com/articles/s41598-017-18398-4  
- ESM Table S1 PDF: https://media.springernature.com/original/springer-static/esm/art%3A10.1038%2Fs41598-017-18398-4/MediaObjects/41598_2017_18398_MOESM1_ESM.pdf  
- Yulian method note: `docs/bass2-data-curation-yulian.md`  
- NASA/TM-20210011385: https://ntrs.nasa.gov/citations/20210011385  

### Table S1 unit audit (Daniel re-check 2026-11-14)

ESM Table S1 prints left header `Vf×10³ (cm/s)` and right header `Vf×10³ (mm/s)`. Magnitudes for
B16 (6.78, 7.62, 6.99, 5.68) match the **cm/s×10³** scale (and Table S2’s cm/s headers). Literal
mm/s×10³ would imply ~6–8 mm/s for thick opposed rods — inconsistent with Fig. 6a narrative
(~0.05–0.08 mm/s). **Interpretation (shared with Yulian):** right header is a typesetting error;
use cm/s×10³.

Conversion used in curated JSON:

```text
Vf_mm_s = (Vf × 10³)_cm_s × 0.01
```

| Trial id | Sample | \(X_{O_2}\) | \(V_g\) (cm/s) | Vf×10³ | Vf (mm/s) curated | Engine pair vs Vg167 |
|---|---|---|---|---|---|---|
| `BASS-II-B16-Vg755` | B16 | 18.2% | 7.55 | 6.78 | 0.0678 | PARTIAL / no Δ |
| `BASS-II-B16-Vg167` | B16 | 18.2% | 1.67 | 7.62 | 0.0762 | (reference) |
| `BASS-II-B16-Vg083` | B16 | 18.2% | 0.83 | 6.99 | 0.0699 | PARTIAL / no Δ |
| `BASS-II-B16-Vg072` | B16 | 18.2% | 0.72 | 5.68 | 0.0568 | PARTIAL / no Δ |
| `BASS-II-B19-Vg755` | B19 | 17.5% | 7.55 | 4.69 | 0.0469 | — |
| `BASS-II-B19-Vg167` | B19 | 17.5% | 1.67 | 6.52 | 0.0652 | vs B16-Vg167: PARTIAL |

**Descriptive non-monotonic check (B16 recorded values only):**  
\(V_f(1.67) > V_f(7.55) > V_f(0.72)\) → 0.0762 > 0.0678 > 0.0568 mm/s, consistent with Fig. 6a
shape. This is **not** exposed as a causal Compare Δ while pressure is unknown and points share
`sample_id=B16`.

### Pair matrix

| Pair | Declared varied | Matched | Uncontrolled / unknown | Level | Deltas | Allowed claim |
|---|---|---|---|---|---|---|
| B16-Vg755 vs B16-Vg167 | `flow_speed` | PMMA, cylinder Ø, thick, opposed, O₂ 18.2% | pressure both null; same sample stepped series | **PARTIAL** | withheld | Descriptive series / Fig. 6a narrative with limitations |
| B16-Vg167 vs B16-Vg072 | `flow_speed` | same as above | pressure; same sample | **PARTIAL** | withheld | Low-flow branch description |
| B16-Vg755 vs B16-Vg072 | `flow_speed` | same | pressure; same sample | **PARTIAL** | withheld | Endpoints of curated B16 Vg span |
| B16-Vg167 vs B19-Vg167 | `oxygen` | PMMA, Ø, thick, opposed, Vg 1.67 | pressure; **different samples**; stepped histories differ | **PARTIAL** | withheld | O₂ association at matched Vg — not a controlled DOE |
| Any B16/B19 vs film row | — | — | geometry sheet vs cylinder; O₂/Vg often unknown on film | **NOT_COMPARABLE** | withheld | None |
| Synthetic SYN-001 vs SYN-002 (fixtures) | `flow_speed` | all controls filled | — | **DIRECT** | allowed | Dev/API only — never NASA |

**Why no real DIRECT today:** curated rod rows omit pressure (`pressure-unknown` tags). Dual-null
pressure is a WARNING. Same `sample_id` adds WARNING (condition points). Engine correctly refuses
to force DIRECT.

### Geometry / units risks

| Risk | Finding | Status |
|---|---|---|
| Pressure None/None treated as match | Fixed → WARNING → PARTIAL | **Resolved in engine** |
| PARTIAL still returning causal deltas | Fixed → withhold + reason | **Resolved in engine** |
| Cylinder `thickness` = diameter | INFO issue on cylinder↔cylinder; schema unchanged | **Documented; data not edited** |
| Table S1 right header mm/s | Re-verified from ESM PDF; cm/s×10³ interpretation held | **Interpreted; residual PDF ambiguity noted** |
| PSI-25 raw ↔ Table S1 row | Not verified file-by-file | **Open (Yulian/PSI access)** |

---

## 4. Flow-regime guide (demo)

1. **Opposed (B16/B19):** oxidizer against spread direction — non-monotonic \(V_f(V_g)\) regime.  
2. **Concurrent:** separate BASS series (NTRS 20150008961) — do not subtract from opposed.  
3. **Quiescent:** not “speed=0 opposed” without evidence.  
4. **Never:** “more ventilation ⇒ always more fire.”

---

## 5. Jury demo recommendation (P1)

**Question:** *How does opposed-flow ventilation change flame spread on PMMA in microgravity?*

**Show:** Explorer sheets for `BASS-II-B16-Vg072`, `…Vg167`, `…Vg755` + Link Fig. 6a / Table S1
provenance. Compare Lab may show **PARTIAL** with withheld deltas and warnings (pressure unknown;
same-sample condition points). Speak the recorded \(V_f\) values **descriptively** and cite the
paper for the non-monotonic claim — do **not** claim an engine causal Δ or three independent
burns.

**Secondary:** B16-Vg167 vs B19-Vg167 at matched \(V_g\) for O₂ association, with explicit
uncontrolled factors (different samples, unknown pressure).

---

## 6. FlameVision (Juanfer)

Link 2018 tracks **flame leading edge** on stills (Fig. S1). That aligns with luminous-edge
tracking, not pyrolysis isotherm or HRR. Keep tracks `unvalidated` until checked against Table S1
\(V_f\). No public video URI on curated rows.

---

## 7. P2 — Confinement

https://link.springer.com/article/10.1007/s12217-024-10106-y — confinement changes O₂ supply /
heat loss. No new tables. Another reason not to pool differently confined setups.

---

## Integration handoff

### Yulian
- Unknown = `null`, never `0`.  
- For future DIRECT flow isolations: document pressure (or agreed N/A flag — needs schema PR).  
- Observational test `test_compare_behavior_observed_for_handoff_to_daniel` still expects old
  behaviour → update to PARTIAL + empty deltas + pressure WARNING.  
- Diameter-vs-thickness schema migration remains post-freeze.

### Alejandro
- `Comparability.PARTIAL` pairs remain groupable; deltas are Compare’s concern.  
- Do not narrate withheld Compare deltas as measured effects.  
- EvidenceTier.DIRECT on B16 can coexist with Comparability.PARTIAL — UI/copy must distinguish.  
- Optional descriptive single-trial mode: coordinate later; no contract change here.

### Marycielo
- Surface `issues` + non-null `withheld_reason`; hide causal Δ charts when withheld.  
- Label condition points / same `sample_id` from tags/notes.  
- Never present SYN-* as NASA.

### Juanfer
- Luminous edge ≠ pyrolysis/temperature.  
- Duplicate timestamps rejected in metrics.

---

## Remaining risks

- No real curated pair reaches DIRECT until pressure (or N/A) is curated.  
- Stepped-flow thermal history couples condition points.  
- Schema diameter-in-thickness ambiguity.  
- PSI row linkage incomplete.  
- 5% tolerance heuristic.
