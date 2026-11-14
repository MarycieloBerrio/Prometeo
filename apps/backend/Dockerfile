# Build from the repo root:  docker build -f apps/backend/Dockerfile .
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.10.4 /uv /uvx /bin/

WORKDIR /app/apps/backend
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

COPY apps/backend/pyproject.toml apps/backend/uv.lock apps/backend/README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY apps/backend/src ./src
RUN uv sync --frozen --no-dev

ENV PATH="/app/apps/backend/.venv/bin:$PATH" \
    PROMETEO_DATA_DIR=/app/data

EXPOSE 8000
CMD ["uvicorn", "prometeo.bootstrap.api:app", "--host", "0.0.0.0", "--port", "8000"]
