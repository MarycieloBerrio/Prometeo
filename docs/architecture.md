# Architecture

## Monorepo

```
apps/backend      FastAPI · Python 3.12 · uv        Evidence Engine API (hexagonal)
apps/frontend     Next.js 16 · TypeScript · pnpm    Dashboard, explorer, comparison lab, FlameVision player
packages/contracts  OpenAPI → TypeScript types      Single source of truth for the HTTP contract
data/             curated evidence, fixtures, (gitignored) raw downloads
infra/db          Postgres + pgvector schema
notebooks/        exploration only, never imported by apps
docs/             architecture, science, ADRs
```

## Hexagonal backend

```
             ┌──────────────── adapters/inbound ────────────────┐
  HTTP ────▶ │ FastAPI routers + DTOs (schemas.py)              │
             └───────────────┬──────────────────────────────────┘
                             ▼
             ┌──────────────── application ─────────────────────┐
             │ use_cases/: Explore, Compare, Coverage,          │
             │             AskResearchAssistant, FlameVision    │
             │ ports/outbound.py: TrialRepository,              │
             │   DocumentRetriever, ExplanationGenerator,       │
             │   FlameFrontDetector                             │
             └───────────────┬──────────────────────────────────┘
                             ▼
             ┌──────────────── domain (pure) ───────────────────┐
             │ Quantity/units · Trial model · filters           │
             │ physics: metrics, compatibility (Physics Validator)│
             │ evidence: EvidenceRank, coverage map             │
             └──────────────────────────────────────────────────┘
                             ▲ implemented by
             ┌──────────────── adapters/outbound ───────────────┐
             │ JSON / Postgres repos · keyword / pgvector retriever│
             │ Claude explainer · offline explainer · OpenCV · NTRS│
             └──────────────────────────────────────────────────┘
  bootstrap/: settings, container (composition root), ASGI app, CLI
```

Rules (enforced by `uv run lint-imports`):

- `bootstrap → adapters → application → domain`, never upward.
- `domain` imports no framework or I/O library (no pydantic, fastapi, httpx, anthropic, cv2…).
- `application` imports no vendor SDK. It talks to the outside only through `ports/`.
- Only `bootstrap/container.py` instantiates outbound adapters.

## Evidence Engine pipeline (Research Assistant)

```
query ─▶ 1 Retrieval ─▶ 2 Physics Validator ─▶ 3 Scientific Analysis ─▶ 4 Evidence Audit ─▶ 5 Explanation
          trials+docs     units, conditions,      deterministic Python      EvidenceRank tier,     LLM prose ONLY
                          compatibility           (v_f, HRR, Pe…)           coverage, limits       from audited packet
                                                                                │
                                                                   tier = insufficient ─▶ refuse, no LLM call
```

## Frontend

```
src/app/            routes (UI, inbound)
src/components/     presentational components
src/domain/         UI-level domain constants (module catalog)
src/application/ports/   EvidenceGateway interface
src/infrastructure/      HttpEvidenceGateway + gateway.ts (composition root, server-only)
```

Pages fetch from Server Components through `gateway`. Request-time data must be wrapped in
`<Suspense>` (Next 16 with Cache Components prerenders a static shell).

## Contracts

`pnpm contracts` = `prometeo export-openapi` → `packages/contracts/openapi.json` →
`openapi-typescript` → `packages/contracts/src/generated.ts`. The frontend imports types from
`@prometeo/contracts` only, so API drift breaks `pnpm typecheck:web`.
