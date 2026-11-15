# Local Windows stack — technical reference

Beginner guide (Spanish): README → *Cómo ejecutar Prometeo en Windows*. This page is the
reference for how the launchers work, every environment variable, and the knowledge base.

## Launchers

| File | Runs | Notes |
|---|---|---|
| `start-prometeo.bat` | `tools/dev/prometeo.ps1 -Action start` | daily start; `--no-browser` |
| `init-prometeo.bat` | `-Action setup` | first-time setup, then start. Flags below |
| `prometeo.bat` | `-Action menu` | start / setup / knowledge base / status / stop |

`init-prometeo.bat` flags (kept from the earlier initializer):

| Flag | Effect |
|---|---|
| `--setup-only` | dependencies + database + validation; do not start API/web |
| `--with-knowledge` | also install the knowledge-base Python packages |
| `--build-kb` | also build the full knowledge base **if it is empty** |
| `--rebuild-kb` | update the knowledge base even if it has data (re-downloads from NASA PSI) |
| `--no-browser` | do not open the browser |

The `.bat` files are thin wrappers (kept CRLF by `.gitattributes`; cmd.exe mis-parses LF batch
files). All logic is in [`tools/dev/prometeo.ps1`](../tools/dev/prometeo.ps1) (Windows
PowerShell 5.1+, ASCII output, works from paths with spaces) and the read-only checks in
[`tools/dev/devcheck.py`](../tools/dev/devcheck.py), which runs in the backend's Python env:

```powershell
uv run --project apps/backend python tools/dev/devcheck.py env          # .env audit, no secrets printed
uv run --project apps/backend python tools/dev/devcheck.py db           # connection, pgvector, schema, KB counts
uv run --project apps/backend python tools/dev/devcheck.py deps         # fastembed / pypdf present?
uv run --project apps/backend python tools/dev/devcheck.py merge-local  # copy legacy .env.local values into .env (backup first)
```

`devcheck.py db` exit codes: `0` ok · `10` unreachable (off / wrong port) · `11` wrong
credentials or database name · `12` tables or migrations incomplete · `13` knowledge base empty
while `PROMETEO_DOCUMENT_STORE=postgres`.

### Guarantees

- **Setup vs start.** `start` installs nothing unless it is missing (`node_modules` older than
  `pnpm-lock.yaml`, no `apps/backend/.venv`, or KB packages missing while the document store is
  postgres). `setup` always runs `pnpm install` and `uv sync`.
- **KB packages are never removed.** Every sync is `uv sync --inexact`, plus `--extra knowledge`
  when the document store is postgres, when asked, or when they are already installed. A bare
  `uv sync` (what the old initializer ran) uninstalls `fastembed`/`pypdf`. `uv run` does not.
- **No duplicates.** Before starting the API (:8000) or web (:3000) the script looks at who
  listens on the port. A healthy Prometeo process is reused. A process from another program is
  reported (name and PID) and never killed. The script warns when the running API is older than
  `.env` (settings are read at start-up).
- **Stop is scoped.** *Stop* kills only the process tree whose command line runs inside this
  repo, climbing only through `uv`/`node`/`python` runners and the console windows the launcher
  opened. It never touches other terminals. PostgreSQL is stopped only on request
  (`docker compose stop db`), never removed.
- **Database safety.** Only `docker compose up -d db` / `stop db`. No `down`, no `-v`, no volume
  or table deletion. If `POSTGRES_PORT` is busy with something that is not Prometeo's container,
  the script stops and suggests a free port. It never changes `.env` on its own.
- **No secrets in output.** Keys and passwords are shown only as *set* / *not set*. Database
  URLs are printed with the password masked.

## Environment variables (repo-root `.env`)

One file, `.env` at the repo root. The API reads it (`settings.py`); docker compose reads it for
`${POSTGRES_*}`; `apps/frontend/next.config.ts` loads its `PROMETEO_*` keys (only those, so no
secret enters the web process). `apps/backend/.env`, if present, is read after the root file
and overrides it, so don't create one. `.env.local` is read by nothing.

| Variable | Read by | Default | Notes |
|---|---|---|---|
| `PROMETEO_ENV` | API | `dev` | `dev`/`test`/`prod` |
| `PROMETEO_DATA_DIR` | API | `<repo>/data` | optional |
| `PROMETEO_TRIAL_FILES` | API | `curated/trials.json` | comma-separated, relative to data dir |
| `PROMETEO_INCLUDE_SYNTHETIC` | API | `false` | |
| `PROMETEO_DOCUMENT_CHUNKS_FILE` | API | `curated/document_chunks.json` | used when document store = json |
| `PROMETEO_TRIAL_STORE` | API | `json` | `postgres` reads trials from the DB |
| `PROMETEO_DATABASE_URL` | API | `postgresql://prometeo:prometeo@localhost:5432/prometeo` | port must equal `POSTGRES_PORT` for the local DB |
| `PROMETEO_DOCUMENT_STORE` | API | `json` | `postgres` = hybrid full-text + pgvector over the KB |
| `PROMETEO_EMBEDDING_MODEL` | API | `BAAI/bge-small-en-v1.5` | must match the model the KB was built with (384-dim) |
| `PROMETEO_PSI_BASE_URL` | API (KB build) | `https://psi.nasa.gov` | optional |
| `PROMETEO_EXPLAINER` | API | `offline` | `anthropic` needs credentials |
| `PROMETEO_ANTHROPIC_MODEL` | API | `claude-sonnet-5-5` | default model |
| `PROMETEO_ANTHROPIC_MODELS` | API | sonnet, opus, haiku 5.5 | picker in the Research Assistant |
| `PROMETEO_ANTHROPIC_EFFORT` | API | `high` | `low`…`max` |
| `ANTHROPIC_API_KEY` | API | — | secret; each teammate their own; or `ant auth login` |
| `PROMETEO_CORS_ORIGINS` | API | `http://localhost:3000` | |
| `PROMETEO_API_URL` | web (server side) | `http://localhost:8000` | |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | docker compose | `prometeo` | applied only when the volume is **first** created |
| `POSTGRES_PORT` | docker compose | `5432` | host port; use e.g. `5433` if 5432 is taken |

Duplicate keys: the **last** one wins (python-dotenv, pydantic-settings and compose agree);
`devcheck.py env` lists them.

## Knowledge base

- Built by `prometeo build-knowledge-base` (`pnpm kb:build`, or menu option 3 / `-Action kb`).
  Option *BASS-II only* passes `--only PSI-25`; the full option indexes every PSI "combustion"
  hit in Combustion Science.
- Stored in the `db-data` Docker volume: it survives container restarts and `docker compose stop`.
- Re-running is safe: catalog rows are upserted, each re-indexed document replaces only its
  own chunks, and raw table rows that NASA no longer publishes are pruned (unless a curated
  trial points at them). No table, volume or other document is deleted.
- Whether it exists is checked **in the database** (chunk counts), not with a marker file, so a
  fresh volume is detected correctly.
- Source files are cached in `data/raw/psi` (gitignored); *Read in the PDF* serves them.

## Sharing one database later (not set up)

Each teammate currently runs their own local Postgres with the same documents indexed. To move
to a shared cloud Postgres (e.g. a managed Postgres with the `vector` extension):

1. Create the database, enable `vector`, apply `infra/db/migrations/*.sql` once.
2. Create **one user per person** (or a read-only role for the API plus one writer role for the
   KB build). Never share the admin password.
3. Require TLS and restrict network access (IP allow-list / private network). Never expose a
   Postgres port publicly without both.
4. Each teammate sets only their own `.env`:
   `PROMETEO_DATABASE_URL=postgresql://<user>:<password>@<host>:5432/prometeo?sslmode=require`.
   The launchers detect a non-localhost URL and skip Docker.
5. Build the knowledge base once from one machine; everybody else just reads.
