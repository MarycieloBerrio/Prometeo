-- Prometeo — evidence store schema (Postgres 17 + pgvector). Rationale: docs/adr/0002-evidence-store.md
-- Applied automatically by docker compose on first start (docker-entrypoint-initdb.d).
-- If you already have a local volume from an older version: `docker compose down -v`, then `pnpm db:up`.
--
-- Shaped after what NASA PSI (https://psi.nasa.gov/physci/repo/search) actually publishes:
--   investigation (PSI-25 = BASS-II, DOI, version, license)
--     ├─ files        hundreds of them, up to hundreds of GB  → `assets` (catalogued, NOT downloaded)
--     ├─ experimental table (CSV, columns differ per investigation) → `raw_test_records` (verbatim)
--     └─ publications / reports                                → `sources` → `document_chunks`
-- Curated, unit-normalized evidence lives in `trials` + `measurements` and always points back
-- to the raw row and the source it came from.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TYPE data_quality AS ENUM ('measured', 'derived', 'extracted', 'unavailable', 'synthetic');

-- ───────────────────────────── Catalog: what exists at NASA ─────────────────────────────

CREATE TABLE investigations (
    id                BIGSERIAL PRIMARY KEY,
    code              TEXT NOT NULL UNIQUE,   -- acronym (BASS-II, FLEX, SAFFIRE-I, SYNTHETIC); PSI accession if none
    psi_accession     TEXT UNIQUE,            -- PSI-25; NULL only for SYNTHETIC
    title             TEXT NOT NULL,
    doi               TEXT,                   -- dataset DOI; PSI requires citing it
    psi_version       INTEGER,                -- PSI dataset version the catalog was read at
    license           TEXT,
    research_area     TEXT,
    sub_research_area TEXT,
    project_type      TEXT,                   -- Microgravity | Ground | Reduced Gravity Investigation
    flight_platform   TEXT,
    hardware          TEXT,                   -- e.g. Microgravity Science Glovebox (MSG)
    start_date        DATE,
    end_date          DATE,
    objectives        TEXT,
    approach          TEXT,
    hypothesis        TEXT,
    psi_metadata      JSONB NOT NULL DEFAULT '{}',  -- remaining PSI fields, verbatim
    retrieved_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE investigation_relations (        -- PSI "Related Investigations" (BASS-II ↔ BASS)
    investigation_id BIGINT NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
    related_id       BIGINT NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
    PRIMARY KEY (investigation_id, related_id)
);

-- Anything that can be cited. `evidence_role` keeps background material (Apollo 1, Mir fire,
-- spinoff articles, outreach video) out of EvidenceRank: it may give context, never evidence.
CREATE TABLE sources (
    id               BIGSERIAL PRIMARY KEY,
    kind             TEXT NOT NULL
                     CHECK (kind IN ('psi_dataset', 'publication', 'report', 'web_page', 'video', 'synthetic')),
    evidence_role    TEXT NOT NULL CHECK (evidence_role IN ('experimental', 'context')),
    investigation_id BIGINT REFERENCES investigations(id),
    reference        TEXT NOT NULL,           -- human-readable citation
    title            TEXT,
    authors          TEXT,
    doi              TEXT,
    url              TEXT,
    source_file      TEXT,
    version          TEXT,
    license          TEXT,
    retrieved_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- File catalog. A row means "this file exists at PSI", not "we have it": local_path/sha256 stay
-- NULL until the file is downloaded into data/raw/. Lets us link trials to videos without
-- pulling 256 GB.
CREATE TABLE assets (
    id               BIGSERIAL PRIMARY KEY,
    investigation_id BIGINT NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
    psi_resource_id  TEXT UNIQUE,             -- PSI's own file id
    file_name        TEXT NOT NULL,
    category         TEXT,                    -- PSI category: Raw Data | Science Documents | Reports | Reference Data | ...
    media_type       TEXT,
    size_bytes       BIGINT,
    remote_url       TEXT,
    psi_version      INTEGER,
    local_path       TEXT,                    -- relative to data/raw/
    sha256           TEXT
);

-- One row of an investigation's experimental table, exactly as published. Columns differ per
-- investigation (BASS-II: "Fan display", "Flow restrictor", "Calibrated initial O2 % by vol"…),
-- so the row is kept as JSONB and never edited. Trials are curated FROM these.
CREATE TABLE raw_test_records (
    id               BIGSERIAL PRIMARY KEY,
    investigation_id BIGINT NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
    asset_id         BIGINT NOT NULL REFERENCES assets(id),   -- the CSV/XLSX it was read from
    row_number       INTEGER NOT NULL,
    test_label       TEXT,                    -- e.g. "B1"
    data             JSONB NOT NULL,          -- { "<column header>": "<cell as text>" }
    UNIQUE (asset_id, row_number)
);

-- ───────────────────────────── Evidence: curated, unit-normalized ─────────────────────────────

CREATE TABLE trials (
    id                TEXT PRIMARY KEY,       -- stable, e.g. BASS-II-B1
    investigation_id  BIGINT NOT NULL REFERENCES investigations(id),
    raw_record_id     BIGINT REFERENCES raw_test_records(id),
    test_label        TEXT,
    sample_id         TEXT,
    test_date         DATE,
    principal_investigator TEXT,
    material          TEXT NOT NULL,
    composition       TEXT,
    geometry          TEXT NOT NULL CHECK (geometry IN ('sheet', 'cylinder', 'sphere', 'droplet', 'other')),
    thermal_regime    TEXT NOT NULL DEFAULT 'unknown' CHECK (thermal_regime IN ('thin', 'thick', 'unknown')),
    flow_direction    TEXT NOT NULL DEFAULT 'unknown'
                      CHECK (flow_direction IN ('concurrent', 'opposed', 'quiescent', 'unknown')),
    -- Conditions. Unknown stays NULL. Each carries its own quality because PSI rarely reports
    -- them directly (BASS-II flow speed must be derived from fan setting + calibration file;
    -- thickness is parsed from free text such as "100 micron PMMA film 2 cm wide").
    thickness_value   DOUBLE PRECISION,
    thickness_unit    TEXT,
    thickness_quality data_quality,
    oxygen_value      DOUBLE PRECISION,
    oxygen_unit       TEXT,
    oxygen_quality    data_quality,
    flow_value        DOUBLE PRECISION,
    flow_unit         TEXT,
    flow_quality      data_quality,
    flow_method       TEXT,
    pressure_value    DOUBLE PRECISION,
    pressure_unit     TEXT,
    pressure_quality  data_quality,
    phenomena         TEXT[] NOT NULL DEFAULT '{}'
                      CHECK (phenomena <@ ARRAY['ignition', 'spread', 'extinction']),
    tags              TEXT[] NOT NULL DEFAULT '{}',
    notes             TEXT,
    source_id         BIGINT NOT NULL REFERENCES sources(id),
    page              TEXT,
    CONSTRAINT thickness_complete CHECK (num_nulls(thickness_value, thickness_unit, thickness_quality) IN (0, 3)),
    CONSTRAINT oxygen_complete    CHECK (num_nulls(oxygen_value, oxygen_unit, oxygen_quality) IN (0, 3)),
    CONSTRAINT flow_complete      CHECK (num_nulls(flow_value, flow_unit, flow_quality) IN (0, 3)),
    CONSTRAINT pressure_complete  CHECK (num_nulls(pressure_value, pressure_unit, pressure_quality) IN (0, 3)),
    CONSTRAINT derived_flow_needs_method CHECK (flow_quality IS DISTINCT FROM 'derived' OR flow_method IS NOT NULL)
);

CREATE TABLE media (
    id        BIGSERIAL PRIMARY KEY,
    trial_id  TEXT NOT NULL REFERENCES trials(id) ON DELETE CASCADE,
    kind      TEXT NOT NULL CHECK (kind IN ('video', 'image')),
    uri       TEXT NOT NULL,
    asset_id  BIGINT REFERENCES assets(id),   -- the catalogued PSI file, when it is one
    start_s   DOUBLE PRECISION,
    end_s     DOUBLE PRECISION,
    source_id BIGINT REFERENCES sources(id)
);

-- FlameVision output. Tracks the luminous leading edge, NOT the reaction front.
CREATE TABLE flame_tracks (
    id              BIGSERIAL PRIMARY KEY,
    trial_id        TEXT NOT NULL REFERENCES trials(id) ON DELETE CASCADE,
    media_id        BIGINT NOT NULL REFERENCES media(id) ON DELETE CASCADE,
    feature         TEXT NOT NULL DEFAULT 'luminous_leading_edge' CHECK (feature IN ('luminous_leading_edge')),
    mm_per_pixel    DOUBLE PRECISION NOT NULL CHECK (mm_per_pixel > 0),
    fps             DOUBLE PRECISION NOT NULL CHECK (fps > 0),
    origin_px       DOUBLE PRECISION NOT NULL DEFAULT 0,
    algorithm       TEXT NOT NULL,            -- detector name + version, for reproducibility
    validation      TEXT NOT NULL DEFAULT 'unvalidated'
                    CHECK (validation IN ('unvalidated', 'validated', 'rejected')),
    validation_note TEXT,
    reference_measurement_id BIGINT,          -- FK added below (circular with measurements)
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT validated_needs_reference CHECK (validation <> 'validated' OR reference_measurement_id IS NOT NULL)
);

CREATE TABLE flame_track_samples (
    track_id    BIGINT NOT NULL REFERENCES flame_tracks(id) ON DELETE CASCADE,
    frame       INTEGER NOT NULL,
    time_s      DOUBLE PRECISION NOT NULL,
    position_mm DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (track_id, frame)
);

CREATE TABLE measurements (
    id                BIGSERIAL PRIMARY KEY,
    trial_id          TEXT NOT NULL REFERENCES trials(id) ON DELETE CASCADE,
    name              TEXT NOT NULL,          -- flame_spread_rate | oxygen_final | co2_final | co_final | ...
    value             DOUBLE PRECISION NOT NULL,
    unit              TEXT NOT NULL,
    uncertainty_value DOUBLE PRECISION,
    uncertainty_unit  TEXT,
    quality           data_quality NOT NULL,
    method            TEXT,                   -- required for 'derived'
    flame_track_id    BIGINT REFERENCES flame_tracks(id) ON DELETE CASCADE,  -- set when derived by FlameVision
    source_id         BIGINT NOT NULL REFERENCES sources(id),
    page              TEXT,
    CONSTRAINT derived_needs_method CHECK (quality <> 'derived' OR method IS NOT NULL),
    CONSTRAINT uncertainty_complete CHECK (num_nulls(uncertainty_value, uncertainty_unit) IN (0, 2))
);

ALTER TABLE flame_tracks
    ADD CONSTRAINT flame_tracks_reference_fk
    FOREIGN KEY (reference_measurement_id) REFERENCES measurements(id) ON DELETE SET NULL;

-- ───────────────────────────── Retrieval: AI context ─────────────────────────────

-- Chunks of reports, papers and pages for hybrid (full-text + vector) retrieval. Indexing is an
-- offline job. The embedding dimension is tied to `embedding_model` (BAAI/bge-small-en-v1.5 =
-- 384); changing the model means a migration and a full re-index.
CREATE TABLE document_chunks (
    id               TEXT PRIMARY KEY,        -- e.g. bass2-summary-p12-1
    source_id        BIGINT NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    asset_id         BIGINT REFERENCES assets(id),
    investigation_id BIGINT REFERENCES investigations(id),   -- denormalized for filtered search
    chunk_index      INTEGER NOT NULL,
    page             TEXT,
    section          TEXT,
    text             TEXT NOT NULL,
    tsv              TSVECTOR GENERATED ALWAYS AS (to_tsvector('english', text)) STORED,
    embedding        VECTOR(384),
    embedding_model  TEXT,
    UNIQUE (source_id, chunk_index),
    CONSTRAINT embedding_has_model CHECK (num_nulls(embedding, embedding_model) IN (0, 2))
);

-- ───────────────────────────── Indexes ─────────────────────────────

CREATE INDEX sources_investigation_idx ON sources (investigation_id);
CREATE INDEX assets_investigation_idx ON assets (investigation_id, category);
CREATE INDEX raw_test_records_investigation_idx ON raw_test_records (investigation_id);
CREATE INDEX trials_investigation_idx ON trials (investigation_id);
CREATE INDEX trials_material_idx ON trials (lower(material));
CREATE INDEX trials_conditions_idx ON trials (oxygen_value, flow_value);   -- coverage map
CREATE INDEX media_trial_idx ON media (trial_id);
CREATE INDEX flame_tracks_trial_idx ON flame_tracks (trial_id);
CREATE INDEX measurements_trial_idx ON measurements (trial_id, name);
CREATE INDEX document_chunks_investigation_idx ON document_chunks (investigation_id);
CREATE INDEX document_chunks_tsv_idx ON document_chunks USING GIN (tsv);
CREATE INDEX document_chunks_embedding_idx ON document_chunks USING hnsw (embedding vector_cosine_ops);
