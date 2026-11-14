# Scientific E2E battery (Yulian) — curated BASS-II

**Branch / PR scope:** `test/yulian-scientific-e2e`  
**Reference main:** `da9ce00` (Physics Validator #7 integrated)  
**Date:** 2026-11-14

## Purpose

Prove the hackathon MVP path against **real curated NASA BASS-II records**, not synthetic fixtures:

Explorer → Comparison Lab → Coverage → Research Assistant → FlameVision artifact honesty.

## How to run

```powershell
cd apps/backend
uv run pytest tests/integration -q
uv run prometeo validate-data
```

The suite builds `TestClient` with explicit settings (no ambient `.env`):

- `trial_files=curated/trials.json`
- `include_synthetic=False`
- `explainer=offline`

## What is asserted

| Check | Expected on current corpus |
|---|---|
| Curated snapshot | 7 trials, 0 synthetic; sample_ids B16/B19 for rod points |
| `GET /health` | `status=ok` |
| `GET /api/v1/trials` | 7 BASS-II ids |
| Trial sheet B16-Vg167 | O₂ 18.2 %, Vg 1.67 cm/s, Vf 0.0762 mm/s, pressure `null`, media `[]` |
| Compare B16 flow | `partially_comparable`, empty deltas, pressure WARNING, values still visible |
| Compare B16/B19 O₂ | `partially_comparable`, empty deltas |
| Compare rod vs film | `not_comparable`, empty deltas |
| Coverage | cells with and without evidence |
| Assistant demo Q | tier ∈ {direct,partial,insufficient}; no SYN- ids in answer |
| FlameVision PSI-25 B9 | `UNVALIDATED`, units `px` / `px/s`, `prometeo_trial_id=null` |

## Demo notes (scientific honesty)

1. **PARTIAL ≠ failure.** Dual-null pressure after PR #7 correctly blocks causal Δ for B16 stepped-flow points. Show each measured FSR; do not invent a ventilation “effect size”.
2. **Condition points ≠ replicates.** Multiple `BASS-II-B16-*` ids are one physical sample under stepped flow.
3. **`geometry.thickness` on cylinders** currently stores **rod diameter** (schema limitation). Do not call it film thickness.
4. **FlameVision** tracks the luminous leading edge in pixels until calibrated and linked to a curated trial id. Page may still say “no verified video” while static artifacts live under `apps/frontend/public/experiments/flamevision/`.
5. **PR #6 (Postgres KB)** remains unmerged: Escenario C (old-schema upgrade) FAIL. Defaults stay JSON.

## Out of scope (do not “fix” by invading teammates)

Physics Validator, EvidenceRank, CompareTrials, Research Assistant core, OpenCV, Marycielo UI, OpenAPI contracts, curated BASS-II values.
