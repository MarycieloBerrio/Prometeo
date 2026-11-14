# Prometeo frontend

Next.js 16 (App Router, Cache Components) · React 19 · TypeScript.

```bash
pnpm dev:web        # from repo root, http://localhost:3000
pnpm typecheck:web
pnpm lint:web
pnpm build:web
```

Needs the API running (`pnpm dev:api`). Configure the URL with `PROMETEO_API_URL`
(default `http://localhost:8000`).

## Structure (ports & adapters)

```
src/app/                    routes — one per product module
src/components/             presentational components (DataQualityBadge, …)
src/domain/                 UI domain constants (module catalog)
src/application/ports/      EvidenceGateway — what the UI needs from the backend
src/infrastructure/         HttpEvidenceGateway + gateway.ts (server-only composition root)
```

API types come from `@prometeo/contracts`. Regenerate them with `pnpm contracts` after backend
DTO changes. Read `AGENTS.md` (here and at the repo root) before editing.
