# BASS-II curated evidence — method note (Yulian)

**Date:** 2026-11-14  
**Branch:** `feat/yulian-bass2-evidence-data`  
**Goal:** First *real* curated trial corpus for Prometeo Explorer / Compare, with honest provenance.

## What was curated

| Count | Content |
|------:|---------|
| **7** | Trial records in `data/curated/trials.json` |
| **6** | Fully conditioned opposed-flow black PMMA rod points (samples B16, B19) |
| **1** | Thin-film context row with intentional unknown O₂ / Vg |
| **8** | Paraphrased document chunks in `data/curated/document_chunks.json` |

No SYNTHETIC investigations. No invented DOIs, video URLs, or defaulted 21% O₂ / 101.3 kPa.

## Primary sources (verified)

1. **Link et al., Sci. Rep. 8:120 (2018)** — CC BY 4.0  
   DOI [10.1038/s41598-017-18398-4](https://doi.org/10.1038/s41598-017-18398-4)  
   Supplementary Table S1 (PDF consulted 2026-11-14).  
   Used for B16 / B19 numeric rows.

2. **NASA/TM-20210011385** — BASS-II Summary Report  
   [NTRS 20210011385](https://ntrs.nasa.gov/citations/20210011385)  
   Used for thin-film 2.2 mm/s textual value (§2.2.5) and qualitative LOC narrative for chunks.

3. **NASA PSI-25** — public metadata  
   [PSI-25](https://psi.nasa.gov/physci/repo/data/investigations/PSI-25), DOI `10.60555/4qc4-de67`, CC0-1.0, ~256 GB.  
   **Not** used for numeric FSR in this PR: bulk file API returned 404 without an authenticated session.

4. **Olson & Ferkul NTRS 20150008961** — concurrent flammability limits (context only; no FSR table curated).

Manifest: `data/sources/bass2-manifest.json`.

## Unit conversion (Table S1)

Table S1 reports `Vf × 10³` with header unit **cm/s** on the left. The right-side header prints `(mm/s)` but the numeric magnitudes match the cm/s×10³ scale (and Table S2 uses cm/s throughout).

Conversion applied after human table parse:

```text
Vf_mm_s = (Vf × 10³)_cm_s × 0.01
```

Example: B16 at Vg = 7.55 cm/s → 6.78 → **0.0678 mm/s**.

Rod `geometry.thickness` stores **diameter** (6.4 mm for 0.64 cm rods), matching the schema’s single thickness slot; notes state this explicitly.  
**TODO(integration):** if the domain later distinguishes diameter vs thickness for cylinders, migrate without inventing new public DTOs in this PR.

## Compare candidates (Daniel owns final physics call)

| Pair | Varied | Why candidate | Status |
|------|--------|---------------|--------|
| `BASS-II-B16-Vg755` vs `BASS-II-B16-Vg167` | `flow_speed` | Same sample id, material, diameter, O₂=18.2%, opposed | **pending Daniel** — same burn sequence |
| `BASS-II-B16-Vg167` vs `BASS-II-B16-Vg072` | `flow_speed` | Non-monotonic FSR (0.0762 → 0.0568 mm/s) | **pending Daniel** |
| `BASS-II-B16-Vg167` vs `BASS-II-B19-Vg167` | `oxygen` | Matched Vg=1.67 cm/s, same geometry | **pending Daniel** |
| Any B16/B19 vs `BASS-II-FILM-100um-…` | — | Thin sheet vs thick cylinder | **not_comparable** (expected) |

**Important:** B16-* (and B19-*) rows are **condition points from stepped-flow burns**, not independent ignitions. Daniel should decide whether Compare may treat them as separate trials.

## Evidence gaps (absence ≠ safety)

- No concurrent-flow `flame_spread_rate` rows.
- No `media[]` URIs (PSI MP4s not publicly fetchable in this pass).
- Pressure omitted on rod rows (not in Table S1).
- Thin-film row omits O₂ and Vg (TM does not bind 2.2 mm/s to one full condition vector).
- Coverage map will be sparse; empty cells mean **no curated evidence**.

## Assistant handoff (Alejandro)

**Questions the corpus can support (with citations):**

1. How does opposed flame spread over thick PMMA rods change with ventilation in BASS-II microgravity (B16 series)?
2. What opposed-flow quenching / low-flow extinction behaviour is reported for thin PMMA films in the BASS-II Summary Report?
3. What limiting-oxygen comparison between microgravity and normal gravity is stated for opposed PMMA rods in TM-20210011385 / Link et al.?

**Questions that should be refused / insufficient:**

1. What is the flame-spread rate for concurrent PMMA rods at 15% O₂ and 20 cm/s in BASS-II? *(no curated concurrent FSR)*
2. Is PMMA “safe” for a lunar habitat at 0.16 g? *(no evidence; wrong gravity regime)*
3. Predict FSR at 12% O₂ and 0.1 cm/s for a 6.4 mm rod. *(extrapolation / untested)*

## FlameVision handoff (Juanfer)

Candidate imagery sources (not attached as `media.uri` until reproducible):

- PSI-25 example raw name from public HTML: `PSI-25_Raw Data_BASS_GMT50_SAMPLE_147_TEST_B1.mp4` (Bhattacharjee thin film B1 / sample 147) — requires PSI package access.
- Link et al. still sequences for B16/B19 (Fig. 4 / Fig. S1) — paper figures, not ISS telemetry video files.
- Scale: luminous leading edge tracking; paper uses ~1 s still cadence and Δt windows in Table S1.

## Reproducibility

```powershell
python tools/nasa_ingest/validate_staging.py data/curated/trials.json
cd apps/backend
uv run prometeo validate-data
uv run pytest tests/data/test_bass2_curated.py -q
```

Ingest docs: `tools/nasa_ingest/README.md`.  
Source audit notes: `notebooks/bass2-source-audit.md`.
