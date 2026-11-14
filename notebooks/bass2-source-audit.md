# BASS-II source audit notes (Yulian)

Text notes only — not an executable notebook. Consulted **2026-11-14**.

## Space Apps challenge resources

- Challenge URL: https://www.spaceappschallenge.org/2026/challenges/flame-in-freefall/?tab=resources
- Automated fetch of the resources tab returned incomplete HTML; challenge root once returned HTTP 500.
- Project `AGENTS.md` designates NASA PSI + BASS-II Summary Report (NTRS) as MVP primary sources. PSI-25 page is publicly reachable and matches that designation.

## NASA PSI-25

| Item | Observation |
|------|-------------|
| URL | https://psi.nasa.gov/physci/repo/data/investigations/PSI-25 |
| DOI | 10.60555/4qc4-de67 |
| License | CC0-1.0 |
| Size | ~255.77 GB (landing page) |
| Metadata HTML | Public; lists PI tables, related publications, example files |
| Example video name | `PSI-25_Raw Data_BASS_GMT50_SAMPLE_147_TEST_B1.mp4` |
| Unauthenticated files API | `.../geode-py/ws/investigations/PSI-25/files` → **404** |
| Decision | Do **not** invent media URLs; keep bulk downloads in `data/raw/` if acquired later |

Example public metadata rows (Bhattacharjee, GMT50) show sample numbers, film thickness, fan/air displays, calibrated O₂ — useful for future film trials, **not** used as FSR evidence here because flame-spread rates were not in that HTML table.

## NTRS TM-20210011385

- Downloaded to `data/raw/ntrs/TM-20210011385.pdf` (gitignored).
- Text extraction used for §2.2.5 (2.2 mm/s) and Ch.4 qualitative LOC.
- Many FSR figures are plots without machine-readable tables; **no figure digitization** performed (would be `extracted` at best, not `measured`).

## Link et al. 2018 + Table S1

- Article: https://www.nature.com/articles/s41598-017-18398-4 (CC BY 4.0)
- Supplement downloaded to `data/raw/nature/41598_2017_18398_MOESM1_ESM.pdf`
- `pdfplumber` extracted Table S1 cleanly (27 rows, dual columns).
- Curated B16 / B19 points transcribed from that extract and cross-checked against paper narrative (Fig. 6a non-monotonic behaviour).

## Concurrent rods (20150008961)

- PDF downloaded; content is flammability **limits**, not a spread-rate matrix.
- Documented as evidence gap; no concurrent FSR invented.

## Acquisition plan if PSI session becomes available

1. Register / sign in to PSI; download only the subset of raw videos + any tabular exports for PMMA rods / films needed for demo.
2. Store under `data/raw/psi25/` (gitignored); record SHA-256 in `data/sources/bass2-manifest.json`.
3. Map PSI sample / test ids to curated `sample_id` without merging distinct burns.
4. Add `media.uri` only for URLs or local paths that are reproducible for the team under the PSI license terms.
5. Re-run `validate_staging` + `prometeo validate-data` + `tests/data/test_bass2_curated.py`.
