# ADR 0002 — Evidence store: one Postgres with pgvector

- **Status:** proposed
- **Date:** 2026-11-14

## Context

The challenge's data source is the NASA PSI repository
(<https://psi.nasa.gov/physci/repo/search>). The other listed resources are background reading
(Researcher's Guide to ISS Combustion Science, NASA Combustion Science pages, Apollo 1, Apollo 13,
Mir fire, three spinoff articles, one outreach video).

What PSI actually exposes, checked on 2026-11-14:

- 133 investigations, **24 in Combustion Science** (BASS, BASS-II, FLEX, FLEX-2, SAFFIRE-I/II/III,
  ACME family, SAME, SPICE, SLICE, CFI, DAFT and several ground investigations).
- Per investigation: descriptive metadata (title, DOI, version, license, platform, hardware,
  objectives, approach), a publication list, one **experimental table** (CSV) and a file list.
- BASS-II (PSI-25, version 4, DOI `10.60555/4qc4-de67`, CC0-1.0): **130 test rows, 694 files,
  about 256 GB**. Files are 296 MP4 videos (18 GB), 264 ZIP image archives (almost all of the
  volume), 125 PDF proof sheets, and a handful of documents: summary report, science
  requirements, ReadMe, test matrices, fan calibration data.
- The BASS-II table columns are instrument settings, not physics: `Test #`, `Date`, `GMT`,
  `Sample #`, `Fuel Sample Material` (free text, e.g. "100 micron PMMA film 2 cm wide"),
  `Flow restrictor`, `Fan display`, `Air display`, radiometer gain, frames shot, initial and final
  O₂, CO₂ and CO. **There is no flow speed in cm/s and no flame spread rate.** Flow speed has to be
  derived from the fan setting and the calibration file; spread rates come from publications or
  from FlameVision.
- Video file names carry the join key (`BASS_GMT50_SAMPLE_147_TEST_B1.mp4` ↔ row B1).

FLEX and SAFFIRE tables were not inspected (the PSI API timed out); assume different columns.

## Decision

1. **One database: Postgres 17 with the pgvector extension.** No separate vector database.
   - The text corpus is small: a few reports and the listed publications per investigation, plus
     ten web pages, give thousands of chunks, not millions.
   - Every retrieved chunk must be joined to its source, investigation and trials to show
     provenance and to filter by investigation. In one database that is a SQL join; with
     Qdrant/Pinecone/Chroma it is a second system to keep in sync.
   - Postgres full-text search (`tsvector`) and pgvector together give hybrid retrieval, which
     matters here because queries contain exact tokens (PMMA, test ids, sample numbers) that embeddings blur.
   - It is already in `docker-compose.yml` and runs on Supabase unchanged.
2. **Embeddings: `BAAI/bge-small-en-v1.5` (384 dimensions), run locally** through ONNX. No API
   key, no network at query time, and CI stays offline. `KeywordRetriever` stays as the fallback.
   The model name is stored on each chunk; changing it means a migration and a re-index.
3. **Three layers in the schema** (`infra/db/migrations/0001_init.sql`):
   - **Catalog** (`investigations`, `sources`, `assets`, `raw_test_records`): what NASA publishes,
     stored verbatim. `assets` lists every PSI file without downloading it. `raw_test_records`
     keeps each experimental-table row as JSONB because columns differ per investigation.
   - **Evidence** (`trials`, `measurements`, `media`, `flame_tracks`, `flame_track_samples`):
     curated, unit-normalized records. Each trial points to its raw row and its source. Each
     condition (O₂, flow, thickness, pressure) has its own data quality, since most are derived or
     parsed, not reported.
   - **Retrieval** (`document_chunks`): text, `tsvector` and embedding in one row.
4. **`sources.evidence_role`** is `experimental` or `context`. The Apollo, Mir and spinoff pages
   are `context`: the assistant may quote them for background, and EvidenceRank ignores them.
5. **Videos and image archives stay out of the database.** The database holds the URL, size and,
   once downloaded, the local path and checksum.

## Consequences

- The whole PSI combustion catalog (24 investigations, file lists, tables) can be loaded as
  metadata in minutes, and the team downloads only the videos it needs.
- The domain `Trial` has no per-condition quality yet. `PostgresTrialRepository` and the JSON
  schema need that field before derived flow speeds can be shown with the right badge.
- Normalizing a raw row into a trial is curation work per investigation (parse material and
  thickness, convert fan setting to cm/s). The schema records the method; it does not do it.
- Vector search with a small English model is weaker on formulas and tables. Tables from reports
  should become `measurements` with provenance, not chunks.
