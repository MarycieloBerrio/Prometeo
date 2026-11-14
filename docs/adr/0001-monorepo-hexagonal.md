# ADR 0001 — Monorepo with hexagonal backend

- **Status:** accepted
- **Date:** 2026-11-14

## Context

Prometeo combines a Python scientific engine (pandas/NumPy/SciPy/OpenCV, LLM explanation) with
a visual TypeScript frontend. It is built during a 48 h hackathon by a small team and must
stay credible scientifically. Results have to be traceable and reproducible, and an LLM must
never be the source of a number.

## Decision

1. **One repository**: `apps/backend`, `apps/frontend`, `packages/contracts`, plus `data`,
   `infra` and `docs`. pnpm workspaces for JS and uv for Python. Root scripts tie them together.
2. **Hexagonal backend**: a pure `domain` (units, trial model, physics metrics, compatibility,
   EvidenceRank), an `application` layer of use cases and ports, `adapters` for HTTP, storage,
   retrieval, LLM and vision, and `bootstrap` as the composition root. import-linter enforces it in CI.
3. **API contract is generated** from FastAPI's OpenAPI into TypeScript types.
4. **JSON-file repository first**, with Postgres + pgvector behind the same port. This lets the
   team curate a small verified BASS-II sample in git before the database exists.
5. **LLM behind `ExplanationGenerator`**, with an offline deterministic implementation. Claude
   is the default real adapter.

## Consequences

- Science rules are unit-testable without servers, keys or data downloads.
- Swapping storage, retrieval or the LLM vendor is a wiring change in `bootstrap/container.py`.
- There is a little more ceremony (DTO mapping, ports) than a flat FastAPI app. We accept it
  because it keeps LLM and I/O concerns out of the scientific core.
