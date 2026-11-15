# PROMETEO

**Scientific Intelligence for Fire Safety in Space.**
*From microgravity fire data to scientific evidence.*

NASA Space Apps Challenge 2026: *Flame in Freefall: AI-Powered Fire Safety Insights from
Microgravity Combustion Data*.

Prometeo is a multimodal scientific intelligence platform. It brings together NASA microgravity
combustion research, experimental data and video (BASS-II, FLEX, SAFFIRE) so engineers can
search, compare and interpret combustion trials. Every conclusion stays traceable to the
experiments behind it, and the platform refuses to extrapolate when the evidence isn't there.

## Quick start (curated MVP)

Default API serves **curated BASS-II JSON** (7 trials, 0 synthetic). No Anthropic key required.
Postgres is started by the Windows initializer (Docker) but the MVP API still reads curated JSON
unless you switch `PROMETEO_DOCUMENT_STORE` / trial store in `.env`.

**Windows (recommended):** double-click or run from the repo root:

```bat
init-prometeo.bat
```

That copies `.env` if missing, runs `pnpm install` + `uv sync`, starts Postgres (`pnpm db:up`),
validates curated data, then opens API (`:8000`) and web (`:3000`) in new consoles.
Use `init-prometeo.bat --setup-only` to skip launching servers, or `--with-knowledge` to also
install the knowledge-base extras (`pnpm kb:build` later).

```powershell
Copy-Item .env.example .env   # optional; defaults already point at curated JSON
pnpm install
cd apps/backend; uv sync; cd ../..

# Terminal 1 — Evidence Engine (curated)
pnpm dev:api              # http://127.0.0.1:8000  (or: uv run prometeo serve --no-reload)

# Terminal 2 — web
pnpm dev:web              # http://localhost:3000
```

Sanity check before demos:

```powershell
cd apps/backend
uv run prometeo validate-data   # expect: OK: 7 trials (0 synthetic)
```

UI-only work without curated semantics: `pnpm dev:api:synthetic` (labels data as
`SYNTHETIC` — never mix into jury claims). Verified smoke notes:
[`docs/integration/mvp-quickstart-smoke-yulian.md`](docs/integration/mvp-quickstart-smoke-yulian.md).

Other settings go in the repo-root `.env` (copy `.env.example`). Keep only that one file: an
`apps/backend/.env` would override it.
Run all checks with `pnpm check`.

## Repository

| Path | What |
|---|---|
| `apps/backend` | Evidence Engine API: FastAPI, hexagonal architecture |
| `apps/frontend` | Next.js dashboard: Explorer, Comparison Lab, FlameVision, Assistant |
| `packages/contracts` | TypeScript API types generated from OpenAPI |
| `data` | Curated evidence (git), synthetic fixtures, raw downloads (ignored) |
| `infra` | Postgres + pgvector schema |
| `docs` | [Architecture](docs/architecture.md) · [Science & limits](docs/science.md) · [ADRs](docs/adr) |

AI agents: start with [AGENTS.md](AGENTS.md).

## Scope and limitations

Prometeo supports knowledge discovery, experimental analysis and preliminary engineering
decisions. It does **not** replace flammability testing, certification, safety standards or
validated full-scale fire models. Microgravity results don't transfer directly to lunar or
Martian partial gravity, and small samples don't predict full-scale fires.
