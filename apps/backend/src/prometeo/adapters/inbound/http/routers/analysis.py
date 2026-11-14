"""Comparison Lab, coverage map and Research Assistant endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from prometeo.adapters.inbound.http import dependencies as deps
from prometeo.adapters.inbound.http.schemas import (
    AskRequest,
    AskResponse,
    CompareRequest,
    CompareResponse,
    CoverageResponse,
    ask_out,
    compare_out,
    coverage_out,
)
from prometeo.application.use_cases.ask_research_assistant import (
    AskResearchAssistant,
    AssistantQuery,
)
from prometeo.application.use_cases.compare_trials import CompareTrials
from prometeo.application.use_cases.coverage_map import BuildCoverageMap
from prometeo.domain.experiments.filters import TrialFilter
from prometeo.domain.experiments.model import FlowDirection, GeometryType

router = APIRouter(prefix="/api/v1", tags=["analysis"])


@router.post("/comparisons", response_model=CompareResponse)
def compare_trials(
    body: CompareRequest, use_case: Annotated[CompareTrials, Depends(deps.compare)]
) -> CompareResponse:
    result = use_case.execute(body.trial_a, body.trial_b, frozenset(body.varied), body.metrics)
    return compare_out(result)


@router.get("/coverage", response_model=CoverageResponse)
def coverage_map(
    use_case: Annotated[BuildCoverageMap, Depends(deps.coverage)],
    include_synthetic: Annotated[bool, Depends(deps.include_synthetic)],
    material: str | None = None,
    geometry: GeometryType | None = None,
    flow_direction: FlowDirection | None = None,
) -> CoverageResponse:
    criteria = TrialFilter(
        material=material,
        geometry=geometry,
        flow_direction=flow_direction,
        include_synthetic=include_synthetic,
    )
    return coverage_out(use_case.execute(criteria))


@router.post("/assistant/ask", response_model=AskResponse)
def ask(
    body: AskRequest,
    use_case: Annotated[AskResearchAssistant, Depends(deps.assistant)],
    include_synthetic: Annotated[bool, Depends(deps.include_synthetic)],
) -> AskResponse:
    criteria = TrialFilter(
        material=body.material,
        geometry=GeometryType(body.geometry) if body.geometry else None,
        flow_direction=FlowDirection(body.flow_direction) if body.flow_direction else None,
        include_synthetic=include_synthetic,
    )
    return ask_out(use_case.execute(AssistantQuery(body.question, criteria, body.metric)))
