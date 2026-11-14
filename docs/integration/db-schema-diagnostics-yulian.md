# DB schema diagnostics (Yulian)

Read-only probe for Postgres volumes after PR #6 merged the knowledge-base migrations.

## Command

```powershell
cd apps/backend
uv run prometeo diagnose-db
```

Uses `PROMETEO_DATABASE_URL` (default `postgresql://prometeo:prometeo@localhost:5432/prometeo`).

## States

| State | Meaning | Operator action |
|---|---|---|
| `fresh` | 0001 + 0002 markers present | OK for KB job |
| `legacy_pre_kb` | Base tables exist; 0002 columns/indexes missing (Escenario C) | Apply `0002_knowledge_base.sql` by hand, or recreate volume with human approval |
| `empty` | No Prometeo tables | `pnpm db:up` on empty volume |
| `partial` | Inconsistent markers / missing `vector` | Inspect output; do not hotfix Alejandro migrations from an unrelated PR |
| `unreachable` | Cannot connect / no driver | Start DB or install `psycopg` |

## Safety

- SELECT / `information_schema` / `pg_catalog` only.
- Never runs `ALTER`, `DROP`, `docker compose down -v`, or edits migration files.
- MVP trial serving remains JSON until `PostgresTrialRepository` is implemented.

## Related

- Migrations: `infra/db/migrations/0001_init.sql`, `0002_knowledge_base.sql`
- ADR: `docs/adr/0002-evidence-store.md`
