# Curated MVP Quick Start smoke (Yulian)

**Date:** 2026-11-14  
**Main tip when verified:** `9dcaa04`  
**Scope:** document + exercise a clean curated start (JSON stores). No architecture
changes. Does not require Postgres or `ANTHROPIC_API_KEY`.

## Expected configuration

Defaults from Settings / `.env.example` (explicit overrides optional):

```text
PROMETEO_TRIAL_STORE=json
PROMETEO_TRIAL_FILES=curated/trials.json
PROMETEO_DOCUMENT_STORE=json
PROMETEO_DOCUMENT_CHUNKS_FILE=curated/document_chunks.json
PROMETEO_INCLUDE_SYNTHETIC=false
PROMETEO_EXPLAINER=offline
```

## Commands executed (PowerShell)

```powershell
cd apps/backend
uv run prometeo validate-data
uv run prometeo serve --no-reload --host 127.0.0.1 --port 8000
```

Second terminal (not required for API smoke): `pnpm dev:web`.

## Smoke results (this session)

| Check | Result |
|---|---|
| `validate-data` | `OK: 7 trials (0 synthetic) from 1 file(s)` |
| `GET /health` | `status=ok` |
| `GET /api/v1/trials` | **7** ids, **0** `is_synthetic` |
| Document chunks file | **8** entries in `data/curated/document_chunks.json` |
| `GET /api/v1/trials/BASS-II-B16-Vg167` | O₂ **18.2 %**, Vg **1.67 cm/s**, Vf **0.0762 mm/s**, pressure **null**, media **[]** |
| `POST /api/v1/comparisons` (`trial_a`/`trial_b`/`varied=["flow_speed"]`) | `level=partially_comparable`, `deltas=[]`, `withheld_reason` set; pressure WARNING visible |
| `GET /api/v1/coverage` | cells returned (54 in this run) |
| `POST /api/v1/assistant/ask` (demo ventilation question) | `tier=direct`, `model=offline-template`, no SYN- trial ids in answer |

Compare body shape (contracts):

```json
{
  "trial_a": "BASS-II-B16-Vg167",
  "trial_b": "BASS-II-B16-Vg755",
  "varied": ["flow_speed"]
}
```

## Honesty notes

- PARTIAL + empty deltas is correct when pressure is dual-null; do not invent a ventilation effect size.
- `pnpm dev:api:synthetic` is for UI layout only — never present as NASA evidence.
- PR #14 (flow derivation) stays unmerged until calibration/identity audit closes
  (`docs/integration/bass2-flow-calibration-audit-yulian.md`).

## Related

- Broader pytest battery: `docs/integration/scientific-e2e-yulian.md`
- Root Quick Start: `README.md`
