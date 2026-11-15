"""FastAPI dependency providers. Use cases are attached to `app.state` by `create_http_app`."""

from __future__ import annotations

from typing import cast

from fastapi import Request

from prometeo.application.use_cases.ask_research_assistant import AskResearchAssistant
from prometeo.application.use_cases.cfd_simulations import GetCfdSimulation, ListCfdSimulations
from prometeo.application.use_cases.compare_trials import CompareTrials
from prometeo.application.use_cases.coverage_map import BuildCoverageMap
from prometeo.application.use_cases.explore_experiments import ExploreExperiments


def explore(request: Request) -> ExploreExperiments:
    return cast(ExploreExperiments, request.app.state.explore)


def compare(request: Request) -> CompareTrials:
    return cast(CompareTrials, request.app.state.compare)


def coverage(request: Request) -> BuildCoverageMap:
    return cast(BuildCoverageMap, request.app.state.coverage)


def assistant(request: Request) -> AskResearchAssistant:
    return cast(AskResearchAssistant, request.app.state.assistant)


def list_cfd(request: Request) -> ListCfdSimulations:
    return cast(ListCfdSimulations, request.app.state.list_cfd)


def get_cfd(request: Request) -> GetCfdSimulation:
    return cast(GetCfdSimulation, request.app.state.get_cfd)


def include_synthetic(request: Request) -> bool:
    return bool(request.app.state.include_synthetic)
