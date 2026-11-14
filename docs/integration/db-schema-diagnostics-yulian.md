# DB schema diagnostics (Yulian)

Read-only probe for Postgres volumes after PR #6 merged the knowledge-base migrations.

## Command

```powershell
cd apps/backend
uv run prometeo diagnose-db
```

Uses `PROMETEO_DATABASE_URL` (default `postgresql://prometeo:prometeo@localhost:5432/prometeo`).

## States

| State | Meaning | Exit code | Operator action |
|---|---|---|---|
| `fresh` | All **11** `0001` tables + `0002` columns/indexes + `vector` | **0** | OK for KB job |
| `legacy_pre_kb` | Base tables exist; 0002 columns/indexes missing (Escenario C) | **1** | Apply `0002_knowledge_base.sql` by hand, or recreate volume with human approval |
| `empty` | No Prometeo tables | **1** | `pnpm db:up` on empty volume |
| `partial` | Inconsistent markers / missing tables / missing `vector` | **1** | Inspect output; do not hotfix Alejandro migrations from an unrelated PR |
| `unreachable` | Cannot connect / no driver | **1** | Start DB or install `psycopg` |

Only `fresh` exits 0 so automation never treats an incompatible volume as validated.

Required tables (from `0001_init.sql`): `investigations`, `investigation_relations`,
`sources`, `assets`, `raw_test_records`, `trials`, `media`, `flame_tracks`,
`flame_track_samples`, `measurements`, `document_chunks`.

## Safety

- SELECT / `information_schema` / `pg_catalog` only.
- Never runs `ALTER`, `DROP`, `docker compose down -v`, or edits migration files.
- MVP trial serving remains JSON until `PostgresTrialRepository` is implemented.

## Related

- Migrations: `infra/db/migrations/0001_init.sql`, `0002_knowledge_base.sql`
- ADR: `docs/adr/0002-evidence-store.md`
