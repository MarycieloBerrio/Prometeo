# AGENTS.md — Prometeo

Guidance for AI coding agents (Claude Code, Codex, Cursor, Copilot…) working in this repository.
Read this file fully before making changes. Folder-level `AGENTS.md` files (e.g.
`apps/frontend/AGENTS.md`) add rules for their subtree.

---

## 1. What Prometeo is

**Prometeo — Scientific Intelligence for Fire Safety in Space.**
Built for the NASA Space Apps Challenge 2026 challenge *Flame in Freefall: AI-Powered Fire Safety
Insights from Microgravity Combustion Data*.

Prometeo turns decades of NASA microgravity combustion research (**BASS-II**, **FLEX**,
**SAFFIRE**, flame-spread modeling) into **verifiable evidence** for spacecraft fire-safety
engineering. It is not a document chatbot or a generic dashboard. It answers:

> *What do we know experimentally about this fuel, under these conditions, with what level of
> evidence, and what are the limits of that conclusion?*

**Core concept: Evidence-Grounded Scientific Intelligence.** Like a RAG system, Prometeo
retrieves documents. It adds a layer that checks the **physical compatibility** of experiments
and the **provenance** of every result. It can and must **refuse to extrapolate** when the data
do not support a conclusion. Uncertainty is a visible product feature.

**Users:** researchers, spacecraft/habitat engineers and mission designers.

### Why fire in microgravity is different
Without buoyant convection, oxygen reaches the flame by diffusion and forced ventilation. This
changes flame shape, stability, spread and extinction. Weak, barely visible flames at low flow
can intensify when ventilation increases, and the response to flow is non-monotonic.

## 2. Product modules

| # | Module | Purpose | Hackathon MVP (Nov 14–15, 2026) |
|---|---|---|---|
| 01 | **Experiment Explorer** | Filter trials by fuel, O₂, ventilation, geometry, phenomenon; trial sheet with media, measurements, sources | Curated, verifiable BASS-II sample |
| 02 | **Combustion Comparison Lab** | Compare ≥2 trials, incompatibility warnings, deltas, **O₂ × ventilation coverage map** | Pairwise comparison + coverage map |
| 03 | **FlameVision** | Overlay the tracked flame front on NASA video, derive spread velocity | One processed **and validated** video |
| 04 | **Research Assistant** | Natural-language Q&A with evidence tier, trials, facts, citations, limitations | Cited answers, rule-based EvidenceRank |
| 05 | **Mission Safety Explorer** | Which evidence applies to a mission scenario, and where the gaps are | Post-MVP |

**Priority above all:** FlameVision + EvidenceRank in one flow. Pick two trials, watch the
original videos, compare measurements, and get an interpretation that states validity limits.

**Recommended demo question:** *How does flame spread over a solid change with ventilation
speed in microgravity?* Use the same material and geometry from BASS-II and two flow conditions.

**Out of scope:** predicting untested conditions, safety certification, "% safe" or "% confidence"
scores, full CFD.

## 3. Repository map

```
AGENTS.md                 ← you are here (CLAUDE.md just points here)
apps/
  backend/                FastAPI · Python 3.12 · uv — Evidence Engine API (hexagonal)
    src/prometeo/
      domain/             PURE: units (Quantity), Trial model, filters, physics metrics,
                          compatibility (Physics Validator), EvidenceRank, coverage, FlameVision model,
                          knowledge (PSI catalog records, text chunking)
      application/        use_cases/ + ports/outbound.py (Protocols)
      adapters/
        inbound/http/     FastAPI routers, DTOs (schemas.py) = public API contract
        outbound/         persistence (JSON, Postgres), retrieval (keyword, pgvector), embeddings, documents,
                          llm (Claude, offline), vision (OpenCV), nasa (PSI, NTRS)
      bootstrap/          settings, container (composition root), api.py (ASGI), cli.py
    tests/                unit/domain, unit/application, api
  frontend/               Next.js 16 · React 19 · TypeScript · pnpm
    src/app/              routes: /explorer /compare /flamevision /assistant /mission-safety
    src/application/ports/ EvidenceGateway interface
    src/infrastructure/   HttpEvidenceGateway + gateway.ts (server-only composition root)
    src/components/  src/domain/
packages/contracts/       OpenAPI → TS types (generated; never edit generated.ts)
data/                     curated/ (evidence, in git) · fixtures/ (SYNTHETIC) · raw/ processed/ (gitignored)
infra/db/migrations/      Postgres + pgvector schema
docs/                     architecture.md · science.md · adr/
notebooks/                exploration only
```

## 4. Commands

Run from the repo root unless noted. Prerequisites: Node ≥ 22, pnpm 11, Python 3.12, uv, Docker (optional).

```bash
pnpm install                                   # JS workspace
(cd apps/backend && uv sync)                   # Python env (+ --extra vision / --extra science)

pnpm dev:api                                   # API on :8000 (docs at /docs)
pnpm dev:web                                   # web on :3000
pnpm db:up                                     # Postgres + pgvector (docker)

pnpm check                                     # everything below
pnpm check:api                                 # ruff + mypy (strict) + import-linter + pytest
pnpm lint:web && pnpm typecheck:web && pnpm build:web
pnpm contracts                                 # regenerate API types after changing backend DTOs
(cd apps/backend && uv run prometeo validate-data)   # parse curated data through the domain

# Knowledge base (offline job: NASA PSI catalog + document chunks → Postgres/pgvector)
(cd apps/backend && uv sync --extra knowledge) # local embeddings (ONNX) + PDF text extraction
pnpm kb:build                                  # all PSI "combustion" hits in Combustion Science
pnpm kb:build --only PSI-25                    # one investigation (BASS-II)
pnpm kb:search "flame spread vs flow speed"    # hybrid full-text + vector search
(cd apps/backend && uv run prometeo derive-bass2-flow)  # BASS-II flow speeds (derived, for review)
```

The Research Assistant reads the knowledge base when `PROMETEO_DOCUMENT_STORE=postgres`
(default `json` = keyword search over `data/curated/document_chunks.json`, used by tests and CI).

UI work without curated data: `pnpm dev:api:synthetic` (= `uv run prometeo serve --synthetic`).
The team develops on Windows/PowerShell, so don't document bash-only `VAR=value cmd` syntax.
Use CLI flags, `.env` files or package scripts instead.

**Definition of done for any change:** `pnpm check` passes, and `pnpm build:web` passes if you
touched the frontend. Add or update tests for domain and application changes.

## 5. Architecture rules (hexagonal)

1. **Dependency direction:** `bootstrap → adapters → application → domain`. Never import upward.
   CI enforces this with `uv run lint-imports` (contracts in `apps/backend/pyproject.toml`).
2. **Domain is pure.** No pydantic, fastapi, httpx, anthropic, psycopg, cv2, pandas or I/O. Use
   frozen dataclasses and enums. Everything is deterministic and unit-testable.
3. **Application talks to the world only through `ports/outbound.py`.** Add a Protocol there
   first, then implement it in `adapters/outbound/`, then wire it in `bootstrap/container.py`.
   That file is the only place adapters are instantiated.
4. **HTTP DTOs live in `adapters/inbound/http/schemas.py`.** Never return domain objects or
   ORM rows from routes. After changing DTOs, run `pnpm contracts`.
5. **Frontend:** pages and components call the `EvidenceGateway` port via `@/infrastructure/gateway`
   (server-only). Never call `fetch` with backend URLs in components. Types come from
   `@prometeo/contracts`; don't hand-write API types.
6. **Next.js 16 is newer than most training data.** Read `apps/frontend/node_modules/next/dist/docs/`
   before using an API. Request-time data (`searchParams`, `fetch`) must be inside `<Suspense>`
   (Cache Components).
7. Keep the offline paths working: JSON repository, `OfflineExplainer`, synthetic fixtures. Tests
   and CI must never need network, API keys or large downloads.

## 6. Scientific integrity rules (most important)

These are product requirements, not style preferences. Breaking them makes the project
scientifically invalid.

1. **The LLM never produces numbers.** All metrics come from deterministic functions in
   `domain/physics/metrics.py`. The explanation model only writes prose from the audited
   `EvidencePacket`.
2. **Pipeline order is fixed:** retrieve → validate (Physics Validator) → compute → audit
   (EvidenceRank, coverage) → explain. If the tier is `insufficient`, refuse and do **not** call
   the LLM.
3. **Every quantity has a unit** (`Quantity`). Every result has **provenance** and a **data
   quality** (`measured`, `derived` with method, `extracted`, `unavailable`, `synthetic`).
   Show quality in the UI next to the value (`DataQualityBadge`).
4. **Never fabricate or fill data.** Don't invent trial values, DOIs, page numbers, video URLs or
   "example NASA results". Unknown stays unknown (`None`). Development data lives only in
   `data/fixtures/` with `investigation: "SYNTHETIC"` and is labelled as such everywhere.
5. **Comparability is explicit.** Different fuel, geometry, thermal regime (thin vs thick) or
   flow direction means `not_comparable`, and deltas are withheld. BASS-II, FLEX and SAFFIRE are
   not one homogeneous dataset.
6. **Absence of evidence ≠ safety.** Empty coverage-map cells and empty search results must say
   "no recorded evidence", never imply a material is safe.
7. **No fake confidence scores.** Use the interpretable tiers `direct`, `partial` and
   `insufficient`. Don't add "% safe" or "% confidence" without a validated statistical model.
8. **FlameVision measures the luminous leading edge**, not the reaction front. Tracks stay
   `unvalidated` until compared with a reference value.
9. **State the limits.** Microgravity ≠ lunar/Martian partial gravity. Small samples ≠
   full-scale fires. Prometeo does not certify materials or predict fire risk.

## 7. Data

See `data/README.md` for the record schema and curation rules. In short: only reviewed records
go into `data/curated/`. Raw downloads (NASA PSI, NTRS PDFs, videos) go into `data/raw/`
(gitignored). Run `prometeo validate-data` after edits. Document indexing (chunking, embeddings)
is an **offline preparation job**, never done per request.

## 8. AI / LLM integration

- Port: `ExplanationGenerator` in `application/ports/outbound.py`.
- Adapters: `adapters/outbound/llm/anthropic_explainer.py` (Claude, `claude-opus-5-5`, document
  blocks with citations enabled, server-side refusal fallback) and `offline_explainer.py`
  (deterministic, the default).
- Select with `PROMETEO_EXPLAINER=anthropic|offline`. Credentials come from `ANTHROPIC_API_KEY`
  or an `ant auth login` profile. Never hardcode keys or commit `.env`.
- Semantic Retrieval is built: `PgVectorRetriever` (hybrid full-text + pgvector) over the knowledge
  base loaded by `BuildKnowledgeBase`; embeddings are local (`TextEmbedder` port, fastembed/ONNX).
- Planned components behind their own ports: Document Intelligence (report extraction → `extracted`
  records for human review), Evidence Ranker.

## 9. Conventions

- **Python:** 3.12, ruff (line length 100), mypy strict, type hints everywhere, `from __future__ import annotations`.
  Domain types are `@dataclass(frozen=True, slots=True)`; enums are `StrEnum`.
- **TypeScript:** strict, `@/*` path alias, Server Components by default, `"use client"` only when needed.
- **Naming:** domain language in English (trial, investigation, flame_spread_rate, ventilation).
  User-facing copy is English for the NASA jury.
- **Tests:** domain logic gets unit tests with explicit units. Use `tests/factories.py`
  (`make_trial`) for test data. API tests use `fastapi.testclient` and the synthetic fixture.
- **Git:** don't commit unless asked. Branch from `main`, keep commits small and descriptive.
  Never commit secrets, `.env`, `data/raw/` or videos.
- When unsure about physics, add a `TODO(science):` and leave the conservative behavior
  (refuse, warn, mark unknown) rather than guessing.
