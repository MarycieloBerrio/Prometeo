-- Prometeo — initial schema (Postgres 17 + pgvector). Mirrors the domain's unified trial record.
-- Applied automatically by docker compose on first start (docker-entrypoint-initdb.d).

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TYPE data_quality AS ENUM ('measured', 'derived', 'extracted', 'unavailable', 'synthetic');

CREATE TABLE sources (
    id           BIGSERIAL PRIMARY KEY,
    reference    TEXT NOT NULL,           -- human-readable citation
    doi          TEXT,
    url          TEXT,
    source_file  TEXT,
    version      TEXT,
    retrieved_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE trials (
    id              TEXT PRIMARY KEY,     -- e.g. BASS-II test id
    investigation   TEXT NOT NULL,        -- BASS-II | FLEX | SAFFIRE-I | ...
    sample_id       TEXT,
    material        TEXT NOT NULL,
    composition     TEXT,
    geometry        TEXT NOT NULL,        -- sheet | cylinder | sphere | droplet | other
    thickness_value DOUBLE PRECISION,
    thickness_unit  TEXT,
    thermal_regime  TEXT NOT NULL DEFAULT 'unknown',
    oxygen_value    DOUBLE PRECISION,
    oxygen_unit     TEXT,
    flow_value      DOUBLE PRECISION,
    flow_unit       TEXT,
    flow_direction  TEXT NOT NULL DEFAULT 'unknown',
    pressure_value  DOUBLE PRECISION,
    pressure_unit   TEXT,
    phenomena       TEXT[] NOT NULL DEFAULT '{}',
    notes           TEXT,
    source_id       BIGINT NOT NULL REFERENCES sources(id),
    page            TEXT
);

CREATE TABLE measurements (
    id                BIGSERIAL PRIMARY KEY,
    trial_id          TEXT NOT NULL REFERENCES trials(id) ON DELETE CASCADE,
    name              TEXT NOT NULL,      -- flame_spread_rate | heat_release_rate | ...
    value             DOUBLE PRECISION NOT NULL,
    unit              TEXT NOT NULL,
    uncertainty_value DOUBLE PRECISION,
    uncertainty_unit  TEXT,
    quality           data_quality NOT NULL,
    method            TEXT,               -- required for 'derived'
    source_id         BIGINT NOT NULL REFERENCES sources(id),
    page              TEXT,
    CONSTRAINT derived_needs_method CHECK (quality <> 'derived' OR method IS NOT NULL)
);

CREATE TABLE media (
    id        BIGSERIAL PRIMARY KEY,
    trial_id  TEXT NOT NULL REFERENCES trials(id) ON DELETE CASCADE,
    kind      TEXT NOT NULL,              -- video | image
    uri       TEXT NOT NULL,
    start_s   DOUBLE PRECISION,
    end_s     DOUBLE PRECISION,
    source_id BIGINT REFERENCES sources(id)
);

-- Document chunks for hybrid (full-text + vector) retrieval. Indexing is an offline job.
-- Embedding dimension must match the embedding model chosen; 1024 is a placeholder.
CREATE TABLE document_chunks (
    id        TEXT PRIMARY KEY,
    source_id BIGINT NOT NULL REFERENCES sources(id),
    page      TEXT,
    text      TEXT NOT NULL,
    tsv       TSVECTOR GENERATED ALWAYS AS (to_tsvector('english', text)) STORED,
    embedding VECTOR(1024)
);

CREATE INDEX trials_material_idx ON trials (lower(material));
CREATE INDEX measurements_trial_idx ON measurements (trial_id, name);
CREATE INDEX document_chunks_tsv_idx ON document_chunks USING GIN (tsv);
CREATE INDEX document_chunks_embedding_idx ON document_chunks USING hnsw (embedding vector_cosine_ops);
