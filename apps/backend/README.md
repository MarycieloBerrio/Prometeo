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

## Knowledge base (Postgres + pgvector)

The Research Assistant's documents come from the NASA PSI repository. Loading them is an offline
job, never done per request:

```bash
pnpm db:up                                              # from the repo root: Postgres + pgvector
uv sync --extra knowledge                               # fastembed (ONNX) + pypdf
uv run prometeo build-knowledge-base                    # PSI search "combustion", Combustion Science
uv run prometeo build-knowledge-base --only PSI-25      # one investigation
uv run prometeo build-knowledge-base --no-documents     # catalog + PSI narrative fields only
uv run prometeo search-knowledge-base "PMMA rod blowoff"
```

What it stores (schema in `infra/db/migrations`):

| Table | Content |
|---|---|
| `investigations`, `investigation_relations` | PSI metadata, verbatim |
| `sources` | the PSI dataset, each listed publication, each indexed document |
| `assets` | every file PSI lists (name, size, folder). Files are **not** downloaded, except the documents that are indexed and the experimental table; those are kept in `data/raw/psi/` |
| `raw_test_records` | experimental-table rows, cells as text. They are **not** trials: curation is a reviewed step |
| `document_chunks` | verbatim text, `tsvector`, 384-d embedding (`BAAI/bge-small-en-v1.5`) |

By default documents in the PSI folders `Reports` and `Science Documents` are indexed
(`--category` adds others, `--max-file-mb` caps the size). The job is safe to re-run. It prints
every document it could **not** index and why: scanned PDFs have no text (there is no OCR), and
`.doc`/`.xlsx` are not read.

Set `PROMETEO_DOCUMENT_STORE=postgres` to make the API search the knowledge base (hybrid
full-text + vector, Reciprocal Rank Fusion). The result `score` only orders results; it is not
a confidence.

## Layout

```
src/prometeo/
  domain/                  # pure science + rules. No frameworks, no I/O.
    shared/                #   Quantity (units), domain errors
    experiments/           #   Trial (unified record), TrialFilter
    physics/               #   metrics (v_f, HRR, Péclet), compatibility (Physics Validator)
    evidence/              #   EvidenceRank tiers, coverage map
    flamevision/           #   flame-front track model
    knowledge/             #   PSI catalog records, text chunking
  application/
    ports/outbound.py      # Protocols the domain/use cases need (repos, retriever, LLM, vision)
    use_cases/             # Explorer, Comparison Lab, Coverage, Research Assistant, FlameVision,
                           # BuildKnowledgeBase (offline)
  adapters/
    inbound/http/          # FastAPI routers + DTOs (driving adapter)
    outbound/              # JSON/Postgres repos, keyword + pgvector retrievers, embeddings,
                           # document text extraction, Claude explainer, OpenCV, PSI, NTRS
  bootstrap/               # settings, composition root (container), ASGI app, CLI
```

Dependency direction: `bootstrap → adapters → application → domain`. Enforced by
import-linter contracts in `pyproject.toml`.

## BASS-II flow speed (curation aid)

The PSI-25 table records the anemometer reading ("Air display"), not the flow speed. NASA's
calibration file (PSI-25, Reference Data, `Fan calibration data.xlsx`) gives
`U [cm/s] = 1.0066 x Air display`, implemented in `domain/physics/fan_calibration.py`.

```bash
uv run prometeo derive-bass2-flow     # writes data/processed/bass2_flow_speeds.json only
# --out must stay under data/processed/; curated/sources/fixtures/.env are refused.
# Pass --overwrite to replace an existing derived worksheet.
```

The output is a worksheet for the curator, not evidence. Every speed is `derived`, is an
estimate (the display resolves about 1 cm/s) and needs review before it enters a curated trial.
Readings outside the calibrated range (2 to 59) and free-text cells ("10 blowoff", "0.5 pot")
are listed and never converted. Speeds published by the investigators take precedence.

## Configuration

All env vars are prefixed `PROMETEO_` — see the repo-root `.env.example`.
`PROMETEO_EXPLAINER=offline` (default) needs no API key; `anthropic` uses Claude
(`ANTHROPIC_API_KEY` or an `ant auth login` profile).
