# BASS-II flow derivation — calibration & identity audit (Yulian)

Independent scientific QA for the BASS-II fan-calibration derivation introduced by
[#14](https://github.com/MarycieloBerrio/Prometeo/pull/14)
(`feat/bass2-flow-derivation`).

**Post-merge status (2026-11-14):** PR #14 is **merged** into `main`
(merge SHA `a3ba620b037d2732f1eb2feaa66213a9f84af0f4`). Merge does **not** close the
calibration checklist below. The formula and the PSI ↔ Link experimental identity
remain **pending documentary verification**. Treat every derived speed as an
estimate for human review, never as curated evidence.

Related containment (also on `main`):

- [#19](https://github.com/MarycieloBerrio/Prometeo/pull/19) — CLI `--out` cannot
  write outside `data/processed/` (protects curated trials).
- [#20](https://github.com/MarycieloBerrio/Prometeo/pull/20) — isolation tests prove
  derivation worksheets do not change curated hashes or B16/B19 measured values.

## What landed in main

Deterministic conversion from PSI-25 anemometer *Air display* to estimated flow:

```text
U [cm/s] = 1.0066 × Air display
```

Attributed in code to NASA PSI-25 Reference Data `Fan calibration data.xlsx`.
CLI: `prometeo derive-bass2-flow` → JSON worksheet under `data/processed/` only
(`derived` quality). Curated `trials.json` ventilation values stay the published
Link et al. speeds and are **not** rewritten by this formula.

## Calibration checklist (must verify against the original workbook)

| # | Check | Status |
|---|---|---|
| 1 | Original sheet name / tab where 1.0066 appears | **open** — workbook not in git (`data/raw/`) |
| 2 | Exact cell / column labeled as the slope | **open** |
| 3 | Instrument definition (“Air display” vs other channels) | **open** |
| 4 | Calibration geometry / duct / sensor placement | **open** |
| 5 | Applicable numeric range (code cites ~2–59; confirm) | **open** — `TODO(science)` in domain |
| 6 | Resolution / precision (notes ~1 cm/s display) | **noted in #14**; no σ in file → none reported |
| 7 | How stepped reading sequences should be interpreted | **open** |
| 8 | NASA wording “example of how to estimate flow” vs universal law | **blocker context** — treat as estimate only |

Until (1)–(5) and (7) are closed from the workbook (or a cited NASA extract),
integrators must **not** promote derived speeds into curated trials or present
1.0066 as a validated measurement in demos.

## WORKBOOK_VERIFICATION

Attempted during Ciclo 11 (integrator workstation):

| Field | Value |
|---|---|
| Status | **BLOCKED** |
| Reason | `Fan calibration data.xlsx` is not present under `data/raw/` (gitignored) and was not downloaded in this session |
| Expected remote name | `Fan calibration data.xlsx` (as cited by #14 / domain docstring) |
| Local path checked | `data/raw/**` — file absent |
| SHA-256 | n/a |
| Sheet / cell | n/a — binary not available |

Do **not** commit the workbook binary until distribution terms and the checklist
above are verified. When a curator places the file under `data/raw/`, update this
table with size, SHA-256, sheet name, and the exact cells that justify 1.0066.

## Experimental identity: Link B16/B19 vs PSI P16/P19

Curated demo trials use ids **B16** / **B19** after Link et al. Table S1
(¼″ black rods, stepped ventilation). In the PSI-25 table:

| Curated / Link label | PSI-25 test with same letter | Likely PSI match (inferred) |
|---|---|---|
| B16 / B19 (rod, ~18 % O₂, stepped flow) | B16 / B19 = 100 µm PMMA films @ 17.3 % O₂ (Bhattacharjee) — **different experiment** | **P16 / P19** (Fernandez-Pello rods) |

This correspondence is **inferred** from material, O₂ and flow sequence; it is
**not** yet proven against the paper or PSI metadata. Linking videos by filename
`…_TEST_B16.mp4` would attach a thin-film asset to a rod trial.

**Integrator rule until proven:** do not auto-join PSI assets to curated B16/B19
by letter alone; prefer published Link speeds over derived anemometer estimates
when they disagree (#14 already documents ~7–20 % gap on P16-like cases).

## Safe posture after merge

- Derived speeds stay `data_quality: derived` with method provenance forever;
  never rewrite as `measured`.
- Do not point Explorer, Compare, FlameVision, or the Research Assistant at the
  derivation worksheet as if it were trial evidence.
- Keep CLI output inside `data/processed/` (#19).
- Keep isolation regressions green (#20).
- When calibration evidence lands in `data/raw/` (gitignored) or a reviewed note
  under `docs/science/`, update the checklist and only then consider promoting
  any estimate into curated records (still as `derived` unless independently
  measured).

## Related

- PR #14 (merged): https://github.com/MarycieloBerrio/Prometeo/pull/14
- Domain: `apps/backend/src/prometeo/domain/physics/fan_calibration.py`
- CLI guard: `apps/backend/src/prometeo/bootstrap/safe_output.py`
- Curated chart consumers: ObservationalSpreadChart (B16/B19) — values from
  curated trials, not from this derivation.
