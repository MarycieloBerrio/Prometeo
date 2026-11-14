# PROMETEO

**Scientific Intelligence for Fire Safety in Space.**
*From microgravity fire data to scientific evidence.*

NASA Space Apps Challenge 2026: *Flame in Freefall: AI-Powered Fire Safety Insights from
Microgravity Combustion Data*.

Prometeo is a multimodal scientific intelligence platform. It brings together NASA microgravity
combustion research, experimental data and video (BASS-II, FLEX, SAFFIRE) so engineers can
search, compare and interpret combustion trials. Every conclusion stays traceable to the
experiments behind it, and the platform refuses to extrapolate when the evidence isn't there.

## Quick start

```bash
cp .env.example .env
pnpm install
(cd apps/backend && uv sync)

# Terminal 1 — API (use the synthetic fixture until curated BASS-II data lands)
cd apps/backend
PROMETEO_TRIAL_FILES=fixtures/synthetic_trials.json PROMETEO_INCLUDE_SYNTHETIC=true uv run prometeo serve

# Terminal 2 — web
pnpm dev:web          # http://localhost:3000
```

On PowerShell, set the env vars with `$env:PROMETEO_TRIAL_FILES="fixtures/synthetic_trials.json"`
(and the same for `PROMETEO_INCLUDE_SYNTHETIC`), or put them in `apps/backend/.env`.

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
