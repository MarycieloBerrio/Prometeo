# data/

| Folder       | In git? | Contents |
|--------------|---------|----------|
| `curated/`   | yes     | **Reviewed** trial records and document chunks. The only source of evidence the app serves. |
| `fixtures/`  | yes     | `SYNTHETIC` records with invented values for UI/API development and tests. Never evidence. |
| `raw/`       | no      | Downloads from NASA PSI / NTRS (PDFs, CSVs, videos). Large; gitignored. |
| `processed/` | no      | Intermediate outputs (extracted tables, FlameVision tracks). Gitignored. |

## Curation rules (non-negotiable)

1. **Every value carries a unit** from the supported list in
   `apps/backend/src/prometeo/domain/shared/quantity.py`. Add units there, never guess.
2. **Every trial and measurement has provenance**: at least a `reference` plus one of
   `doi`, `url` or `source_file`, and the `page`/table where the value appears.
3. **`quality` is honest**:
   - `measured`: value reported in a NASA source and checked by a human against that source.
   - `derived`: computed by Prometeo from measured data; `method` is required.
   - `extracted`: pulled automatically from a document and not yet reviewed.
   - `unavailable`: the quantity is known to be missing.
   - `synthetic`: fixtures only.
4. **Never fill gaps.** If O₂, flow, pressure or thickness is not documented, omit it. The engine
   treats unknowns explicitly. Empty cells in the coverage map mean "no evidence", not "safe".
5. Run `uv run prometeo validate-data` (from `apps/backend`) after every edit.

## Trial record schema (`curated/trials.json`)

```jsonc
{
  "id": "BASS-II-…",                 // stable, unique
  "investigation": "BASS-II",        // BASS-II | FLEX | SAFFIRE-I | FLAME-SPREAD-MODELING
  "sample_id": "…",
  "fuel": { "material": "PMMA", "composition": null },
  "geometry": { "type": "sheet", "thickness": { "value": 1.0, "unit": "mm" }, "thermal_regime": "thick" },
  "oxygen": { "value": 21, "unit": "%" },
  "ventilation": { "speed": { "value": 10, "unit": "cm/s" }, "direction": "concurrent" },
  "pressure": { "value": 101.3, "unit": "kPa" },
  "phenomena": ["ignition", "spread", "extinction"],
  "provenance": { "reference": "…", "doi": "…", "url": "…", "page": "…" },
  "results": [
    { "name": "flame_spread_rate", "value": { "value": 0.0, "unit": "mm/s" },
      "quality": "measured", "uncertainty": null, "method": null,
      "provenance": { "reference": "…", "page": "Table 3" } }
  ],
  "media": [{ "kind": "video", "uri": "…", "start_s": 0, "end_s": 60 }],
  "notes": null
}
```

## Document chunks (`curated/document_chunks.json`)

```json
[{ "id": "bass2-summary-p12-1", "text": "…", "provenance": { "reference": "…", "page": "12", "url": "…" } }]
```

## Knowledge base (Postgres)

`prometeo build-knowledge-base` loads the PSI catalog and document chunks into Postgres
(see `apps/backend/README.md`). The files it downloads (experimental tables, reports) are cached
in `raw/psi/<accession>/`. `curated/document_chunks.json` stays as the offline fallback for
tests and CI. Experimental-table rows land in `raw_test_records` as text; turning a row into a
trial is still the reviewed curation described above.

## Primary sources

- **BASS-II** (MVP): NASA Physical Sciences Informatics (PSI) repository + BASS-II Summary Report (NTRS).
- **FLEX**, **SAFFIRE-I**, flame spread modeling: context in the MVP, integrated afterwards.
- Check which PSI files can be downloaded and linked to the right metadata **before** promising
  a quantitative result. This is the project's biggest technical risk.
