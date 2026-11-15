"""ASGI entry point: `uvicorn prometeo.bootstrap.api:app`."""

from __future__ import annotations

from fastapi import FastAPI

from prometeo.adapters.inbound.http.app import create_http_app
from prometeo.bootstrap.container import Container, build_container
from prometeo.bootstrap.settings import get_settings


def build_app(container: Container) -> FastAPI:
    s = container.settings
    return create_http_app(
        explore=container.explore,
        compare=container.compare,
        coverage=container.coverage,
        assistant=container.assistant,
        source_document=container.source_document,
        assistant_models=container.explainer_models,
        cors_origins=[o.strip() for o in s.cors_origins.split(",") if o.strip()],
        include_synthetic=s.include_synthetic,
    )


app = build_app(build_container(get_settings()))
