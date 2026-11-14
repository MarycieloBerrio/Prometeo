# BASS-II curated evidence — method note (Yulian)

**Date:** 2026-11-14 (hardened)  
**Branch:** `feat/yulian-bass2-evidence-data`  
**PR:** https://github.com/MarycieloBerrio/Prometeo/pull/1  
**Goal:** First *real* curated trial corpus for Prometeo Explorer / Compare, with honest provenance.

## What was curated

| Count | Content |
|------:|---------|
| **7** | Trial records in `data/curated/trials.json` |
| **6** | Fully conditioned opposed-flow black PMMA rod **condition points** (physical samples **B16**, **B19**) |
| **1** | Thin-film context row with intentional unknown O₂ / Vg / pressure |
| **8** | Paraphrased document chunks in `data/curated/document_chunks.json` |

No SYNTHETIC investigations. No invented DOIs, video URLs, or defaulted 21% O₂ / 101.3 kPa.

**Physical samples vs trial ids:** there are **2** physical rod samples (B16, B19) and **4+2** condition-point trial ids from stepped opposed-flow burns. Tags include `condition-point`, `physical-sample-B16|B19`, `not-independent-replicate`.

## Primary sources (verified)

1. **Link et al., Sci. Rep. 8:120 (2018)** — CC BY 4.0 (peer-reviewed; **not** a PSI download)  
   DOI [10.1038/s41598-017-18398-4](https://doi.org/10.1038/s41598-017-18398-4)  
   Supplementary Table S1 (PDF re-parsed with pdfplumber 2026-11-14).  
   Used for B16 / B19 numeric rows.

2. **NASA/TM-20210011385** — BASS-II Summary Report  
   [NTRS 20210011385](https://ntrs.nasa.gov/citations/20210011385)  
   Used for thin-film 2.2 mm/s textual value (§2.2.5) and qualitative LOC narrative for chunks.

3. **NASA PSI-25** — public metadata / package index  
   [PSI-25](https://psi.nasa.gov/physci/repo/data/investigations/PSI-25), DOI `10.60555/4qc4-de67`, CC0-1.0, ~256 GB.  
   **Not** used for numeric FSR in this PR. Do not present Link et al. Table S1 values as if they were transcribed from PSI raw files.

4. **Olson & Ferkul NTRS 20150008961** — concurrent flammability limits (context only; no FSR table curated).

Manifest: `data/sources/bass2-manifest.json`.

## Unit conversion (Table S1) — dimensional audit

Table S1 dual-column header (pdfplumber 2026-11-14):

| Side | Header printed | Interpretation used |
|------|----------------|---------------------|
| Left | `Vf×10³ (cm/s)` | Canonical |
| Right | `Vf×10³ (mm/s)` | **Treated as typesetting error** |

**Argument:** right-column magnitudes (e.g. B16: 6.78, 7.62, 6.99, 5.68) match the same order as left-column cm/s×10³ values and Table S2’s cm/s×10³ scale. If the right header were literal mm/s×10³, FSR would be ~6–8 mm/s for thick opposed rods — physically inconsistent with the paper’s narrative and typical thick-PMMA opposed rates (~0.05–0.1 mm/s). Table S2 uses `(cm/s)` on both sides.

Conversion after human table parse:

```text
Vf_mm_s = (Vf × 10³)_cm_s × 0.01
```

| Trial id | Sample | O₂ % | Vg cm/s | Vf×10³ | Vf mm/s |
|----------|--------|------|---------|--------|---------|
| BASS-II-B16-Vg755 | B16 | 18.2 | 7.55 | 6.78 | 0.0678 |
| BASS-II-B16-Vg167 | B16 | 18.2 | 1.67 | 7.62 | 0.0762 |
| BASS-II-B16-Vg083 | B16 | 18.2 | 0.83 | 6.99 | 0.0699 |
| BASS-II-B16-Vg072 | B16 | 18.2 | 0.72 | 5.68 | 0.0568 |
| BASS-II-B19-Vg755 | B19 | 17.5 | 7.55 | 4.69 | 0.0469 |
| BASS-II-B19-Vg167 | B19 | 17.5 | 1.67 | 6.52 | 0.0652 |

Quality remains `measured` (published table values transcribed + unit-normalized). Notes state the conversion. Not marked `derived` because no new physical metric was computed beyond unit change.

## Schema limitation: cylinder `geometry.thickness` = diameter

Frozen schema / codec expose a single `geometry.thickness` slot. For rods we store **diameter = 6.4 mm** (0.64 cm from Table S1 / paper). Tags: `geometry-thickness-means-diameter`. Notes start with `SCHEMA LIMITATION: … DIAMETER`.

**Not fixed in domain** (Daniel / integration owns `model.py` / DTOs). Proposed later migration:

1. Add optional `geometry.diameter` (or `characteristic_size`) in domain + codec + OpenAPI.
2. Backfill rod rows: move 6.4 mm to `diameter`; leave `thickness` null for cylinders.
3. Keep sheet `thickness` as film thickness.
4. Physics Validator: compare diameter for cylinders, thickness for sheets; never equate across geometry types by the shared slot alone.

Until then: UI/compare consumers must read notes/tags; tests assert cylinder vs sheet regimes differ.

## Compare candidates (Daniel owns final physics call)

| Pair | Varied | Why candidate | Status |
|------|--------|---------------|--------|
| `BASS-II-B16-Vg755` vs `BASS-II-B16-Vg167` | `flow_speed` | Same sample id, material, diameter, O₂=18.2%, opposed | **pending Daniel** — same burn sequence |
| `BASS-II-B16-Vg167` vs `BASS-II-B16-Vg072` | `flow_speed` | Non-monotonic FSR (0.0762 → 0.0568 mm/s) | **pending Daniel** |
| `BASS-II-B16-Vg167` vs `BASS-II-B19-Vg167` | `oxygen` | Matched Vg=1.67 cm/s, same geometry | **pending Daniel** |
| Any B16/B19 vs film row | — | Thin sheet vs thick cylinder | **not_comparable** (observed in tests) |

## Integration risks observed (not patched — out of Yulian scope)

Reproduced via `CompareTrials` / `assess_compatibility` against curated JSON in `tests/data/test_bass2_table_s1_semantics.py` (read-only of Daniel’s modules):

| Issue | Observed | Expected (proposal) | Owner |
|-------|----------|---------------------|-------|
| Pressure `None`/`None` | No warning; treated as match (`compatibility.py` `_numeric_issue`) | Warning: “both undocumented — equality not established” | Daniel |
| Partial comparability | `compare_trials.py` still returns **deltas** whenever level ≠ `not_comparable` | Withhold or clearly label deltas when `partially_comparable` | Daniel |
| Stepped-flow condition points | Distinct trial ids share `sample_id`; Compare treats as independent trials | Flag / refuse causal “effect of flow” unless same-sample stepped series is allowed | Daniel |
| Empty `media[]` | API returns `[]` | UI must not invent a player (Marycielo) | Marycielo |
| Frontend CI `PageProps` | Fails without `next typegen` | Fixed in **PR #2** (`fix/ci-next-typegen-yulian`) | Yulian CI PR |

**Proposed (unapplied) Daniel patch sketch** for pressure:

```python
# in _numeric_issue — DO NOT APPLY HERE
if qa is None and qb is None:
    return _warn(var, "Both trials lack this controlled quantity; match not established")
```

**Proposed (unapplied) delta withhold:**

```python
# in CompareTrials.execute — DO NOT APPLY HERE
if report.level is Comparability.PARTIAL:
    return ComparisonResult(..., (), "Deltas withheld under partial comparability")
```

## Evidence gaps (absence ≠ safety)

- No concurrent-flow `flame_spread_rate` rows.
- No `media[]` URIs (PSI MP4s not publicly fetchable in this pass).
- Pressure omitted on rod rows (not in Table S1).
- Thin-film row omits O₂ and Vg (TM does not bind 2.2 mm/s to one full condition vector).
- Coverage map will be sparse; empty cells mean **no curated evidence**.

## Assistant handoff (Alejandro)

**Supported (cited) questions:** opposed thick-rod ventilation response (B16); thin-film extinction narrative (TM); µg vs 1g LOC statements (TM / Link).  
**Refuse:** concurrent FSR at untested conditions; “is PMMA safe”; extrapolated predictions.  
Chunk `bass2-evidence-absence-not-safety` is a **curation rule**, not a NASA experimental finding.

## FlameVision handoff (Juanfer)

No verified public video URI attached. PSI example filename from public HTML: `PSI-25_Raw Data_BASS_GMT50_SAMPLE_147_TEST_B1.mp4` (requires PSI access). Link et al. Fig. 4 / S1 are still sequences for B16/B19.

## CI handoff

Frontend typecheck on PR #1 failed because CI lacked `next typegen`. Separate PR: https://github.com/MarycieloBerrio/Prometeo/pull/2  
After PR #2 merges to `main`, re-run checks on PR #1 (or rebase/ff only if integrator requests — do not force-push).

## Reproducibility

```powershell
python tools/nasa_ingest/validate_staging.py data/curated/trials.json
cd apps/backend
uv run prometeo validate-data
uv run pytest tests/data -q
uv run ruff check .
uv run mypy
uv run lint-imports
uv run pytest -q
```
