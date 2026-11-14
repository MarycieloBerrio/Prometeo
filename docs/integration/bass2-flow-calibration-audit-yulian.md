# BASS-II flow derivation — calibration & identity audit (Yulian)

Independent scientific QA for open PR
[#14](https://github.com/MarycieloBerrio/Prometeo/pull/14)
(`feat/bass2-flow-derivation`). **Do not merge until the checklist below is
closed or explicitly waived by the science lead with documented limits.**

## What the PR claims

Deterministic conversion from PSI-25 anemometer *Air display* to estimated flow:

```text
U [cm/s] = 1.0066 × Air display
```

Attributed to NASA PSI-25 Reference Data `Fan calibration data.xlsx`. Output is
written as a curator worksheet (`derived` quality), not curated trial evidence.

## Calibration checklist (must verify against the original workbook)

| # | Check | Status |
|---|---|---|
| 1 | Original sheet name / tab where 1.0066 appears | **open** — file not in git (`data/raw/`) |
| 2 | Exact cell / column labeled as the slope | **open** |
| 3 | Instrument definition (“Air display” vs other channels) | **open** |
| 4 | Calibration geometry / duct / sensor placement | **open** |
| 5 | Applicable numeric range (PR cites ~2–59; confirm) | **open** — `TODO(science)` already in PR |
| 6 | Resolution / precision (PR notes ~1 cm/s display) | **noted in PR**; no σ in file → none reported |
| 7 | How stepped reading sequences should be interpreted | **open** |
| 8 | NASA wording “example of how to estimate flow” vs universal law | **blocker context** — treat as estimate only |

Until (1)–(5) and (7) are closed from the workbook (or a cited NASA extract),
integrators must **not** squash-merge #14 into `main` solely because CI is green.

## Experimental identity: Link B16/B19 vs PSI P16/P19

Curated demo trials use ids **B16** / **B19** after Link et al. Table S1
(¼″ black rods, stepped ventilation). Alejandro’s PR notes that in the PSI-25
table:

| Curated / Link label | PSI-25 test with same letter | Likely PSI match (inferred) |
|---|---|---|
| B16 / B19 (rod, ~18 % O₂, stepped flow) | B16 / B19 = 100 µm PMMA films @ 17.3 % O₂ (Bhattacharjee) — **different experiment** | **P16 / P19** (Fernandez-Pello rods) |

This correspondence is **inferred** from material, O₂ and flow sequence; it is
**not** yet proven against the paper or PSI metadata. Linking videos by filename
`…_TEST_B16.mp4` would attach a thin-film asset to a rod trial.

**Integrator rule until proven:** do not auto-join PSI assets to curated B16/B19
by letter alone; prefer published Link speeds over derived anemometer estimates
when they disagree (PR already documents ~7–20 % gap on P16-like cases).

## Safe interim posture

- Keep #14 open; CI green is necessary but not sufficient.
- Harden DB diagnostics separately so incomplete schemas cannot look “fresh”.
- When calibration evidence lands in `data/raw/` (gitignored) or a reviewed note
  under `docs/science/`, update this table and only then consider merge.
- Derived speeds stay `data_quality: derived` with method provenance forever;
  never rewrite as `measured`.

## Related

- PR: https://github.com/MarycieloBerrio/Prometeo/pull/14
- Domain (on PR branch): `apps/backend/src/prometeo/domain/physics/fan_calibration.py`
- Curated chart consumers: ObservationalSpreadChart (B16/B19) — values from
  curated trials, not from this derivation.
