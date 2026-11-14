# Prometeo backend — Evidence Engine API

FastAPI + Python 3.12, hexagonal architecture (ports & adapters). Managed with [uv](https://docs.astral.sh/uv/).

```bash
uv sync                               # install (add --extra vision / --extra science when needed)
uv run prometeo serve                 # http://127.0.0.1:8000  (docs at /docs)
uv run pytest                         # tests
uv run ruff check . && uv run mypy    # lint + types
uv run lint-imports                   # enforce hexagonal dependency rules
uv run prometeo validate-data         # parse curated data through the domain model
uv run prometeo export-openapi        # refresh packages/contracts/openapi.json
```

## Layout

```
src/prometeo/
  domain/                  # pure science + rules. No frameworks, no I/O.
    shared/                #   Quantity (units), domain errors
    experiments/           #   Trial (unified record), TrialFilter
    physics/               #   metrics (v_f, HRR, Péclet), compatibility (Physics Validator)
    evidence/              #   EvidenceRank tiers, coverage map
    flamevision/           #   flame-front track model
  application/
    ports/outbound.py      # Protocols the domain/use cases need (repos, retriever, LLM, vision)
    use_cases/             # Explorer, Comparison Lab, Coverage, Research Assistant, FlameVision
  adapters/
    inbound/http/          # FastAPI routers + DTOs (driving adapter)
    outbound/              # JSON/Postgres repos, keyword retriever, Claude explainer, OpenCV, NTRS
  bootstrap/               # settings, composition root (container), ASGI app, CLI
```

Dependency direction: `bootstrap → adapters → application → domain`. Enforced by
import-linter contracts in `pyproject.toml`.

## Configuration

All env vars are prefixed `PROMETEO_` — see the repo-root `.env.example`.
`PROMETEO_EXPLAINER=offline` (default) needs no API key; `anthropic` uses Claude
(`ANTHROPIC_API_KEY` or an `ant auth login` profile).
