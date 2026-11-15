"""FastAPI application factory (inbound HTTP adapter).

Receives already-built use cases; it never constructs outbound adapters itself.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from prometeo import __version__
from prometeo.adapters.inbound.http.routers import analysis, cfd, experiments
from prometeo.application.use_cases.ask_research_assistant import AskResearchAssistant
from prometeo.application.use_cases.cfd_simulations import GetCfdSimulation, ListCfdSimulations
from prometeo.application.use_cases.compare_trials import CompareTrials
from prometeo.application.use_cases.coverage_map import BuildCoverageMap
from prometeo.application.use_cases.explore_experiments import ExploreExperiments
from prometeo.domain.shared.errors import DomainError, NotFoundError


def create_http_app(
    *,
    explore: ExploreExperiments,
    compare: CompareTrials,
    coverage: BuildCoverageMap,
    assistant: AskResearchAssistant,
    list_cfd: ListCfdSimulations,
    get_cfd: GetCfdSimulation,
    cors_origins: list[str],
    include_synthetic: bool,
) -> FastAPI:
    app = FastAPI(
        title="Prometeo Evidence Engine API",
        version=__version__,
        description="Evidence-grounded scientific intelligence for microgravity combustion.",
    )
    app.state.explore = explore
    app.state.compare = compare
    app.state.coverage = coverage
    app.state.assistant = assistant
    app.state.list_cfd = list_cfd
    app.state.get_cfd = get_cfd
    app.state.include_synthetic = include_synthetic

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(NotFoundError)
    async def _not_found(_: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(DomainError)
    async def _domain(_: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.get("/health", tags=["meta"])
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    app.include_router(experiments.router)
    app.include_router(analysis.router)
    app.include_router(cfd.router)
    return app
