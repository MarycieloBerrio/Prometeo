-- Prometeo — knowledge-base ingestion keys. Safe to run more than once.
-- Applied automatically after 0001 on a fresh volume. On an existing database run it by hand:
--   docker compose exec -T db psql -U prometeo -d prometeo -f /docker-entrypoint-initdb.d/0002_knowledge_base.sql
--
-- Found while loading the real PSI catalog (2026-11-14):
--   * PSI's `resource_id` is NOT a file id. All files of one PSI resource share it (BASS-II:
--     694 files, 7 resource ids), so it cannot be UNIQUE. The file's natural key is its
--     `remote_path`.
--   * The ingestion job is re-runnable, so sources need a stable natural key to upsert on.

ALTER TABLE assets DROP CONSTRAINT IF EXISTS assets_psi_resource_id_key;
ALTER TABLE assets ADD COLUMN IF NOT EXISTS remote_path TEXT;      -- /Home/psi-data/PSI-25/Reports/…
ALTER TABLE assets ADD COLUMN IF NOT EXISTS subcategory TEXT;      -- e.g. Reduced Gravity/Olson/O5
CREATE UNIQUE INDEX IF NOT EXISTS assets_investigation_remote_path_key
    ON assets (investigation_id, remote_path);
CREATE INDEX IF NOT EXISTS assets_psi_resource_idx ON assets (psi_resource_id);

-- psi:PSI-25:dataset | psi:PSI-25:publication:<doi> | psi:PSI-25:file:<remote_path>
-- NULL for hand-curated sources.
ALTER TABLE sources ADD COLUMN IF NOT EXISTS source_key TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS sources_source_key_key ON sources (source_key);
