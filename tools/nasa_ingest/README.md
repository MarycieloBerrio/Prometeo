# NASA ingest utilities (Yulian)

Stdlib-only helpers to validate a **human-reviewed** staging JSON file and optionally
write `data/curated/trials.json` with stable key ordering.

These scripts do **not** scrape NASA, invent numbers, or call LLMs.

## Workflow

1. Manually extract table rows from a primary source into a staging JSON
   (see `examples/staging_bass2_link2018_b16b19.json`).
2. Dry-run validation:

```powershell
python tools/nasa_ingest/validate_staging.py data/processed/staging_trials.json
```

3. Export curated file (refuses overwrite unless `--force`):

```powershell
python tools/nasa_ingest/export_curated_trials.py `
  data/processed/staging_trials.json `
  data/curated/trials.json
```

4. Parse through the domain model:

```powershell
cd apps/backend
uv run prometeo validate-data
uv run pytest tests/data/test_bass2_curated.py -q
```

## What validation rejects

- Duplicate `id`
- `investigation` equal to `SYNTHETIC`
- Missing trial/result `provenance.reference`
- Provenance that is not traceable (`doi` / `url` / `source_file` all absent)
- Invalid `quality` enum values
- Unknown units (checked against the same unit list as the domain)
- Oxygen outside `(0, 100]` percent (or `(0, 1]` fraction)
- Negative flow speeds or flame-spread rates
- `localhost` / `127.0.0.1` URIs in provenance or media
- `quality=derived` without `method`
- `quality=synthetic` in curated staging
