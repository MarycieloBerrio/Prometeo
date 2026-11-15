"""Comparison Lab, coverage map and Research Assistant endpoints."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from prometeo.adapters.inbound.http import dependencies as deps
from prometeo.adapters.inbound.http.schemas import (
    AskRequest,
    AskResponse,
    AssistantModelsResponse,
    CompareRequest,
    CompareResponse,
    CoverageResponse,
    ask_out,
    compare_out,
    coverage_out,
    models_out,
)
from prometeo.application.ports.outbound import ExplainerModel
from prometeo.application.use_cases.ask_research_assistant import (
    AskResearchAssistant,
    AssistantQuery,
)
from prometeo.application.use_cases.compare_trials import CompareTrials
from prometeo.application.use_cases.coverage_map import BuildCoverageMap
from prometeo.application.use_cases.locate_source_document import LocateSourceDocument
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


@router.get("/assistant/models", response_model=AssistantModelsResponse)
def assistant_models(
    models: Annotated[Sequence[ExplainerModel], Depends(deps.assistant_models)],
) -> AssistantModelsResponse:
    """Models a question may pick to write its interpretation (empty: none configured)."""
    return models_out(models)


@router.get(
    "/documents/{chunk_id}/file",
    response_class=FileResponse,
    responses={404: {"description": "No local copy of the source file"}},
)
def source_document_file(
    chunk_id: str,
    use_case: Annotated[LocateSourceDocument, Depends(deps.source_document)],
) -> FileResponse:
    """The original document a retrieved excerpt was extracted from, to show it in place."""
    found = use_case.execute(chunk_id)
    return FileResponse(
        found.path,
        media_type=found.media_type,
        filename=found.file_name,
        content_disposition_type="inline",
    )


@router.post("/assistant/ask", response_model=AskResponse)
def ask(
    body: AskRequest,
    use_case: Annotated[AskResearchAssistant, Depends(deps.assistant)],
    include_synthetic: Annotated[bool, Depends(deps.include_synthetic)],
    models: Annotated[Sequence[ExplainerModel], Depends(deps.assistant_models)],
) -> AskResponse:
    offered = {m.id for m in models}
    # With no language model configured the choice is meaningless and is ignored.
    if body.model is not None and offered and body.model not in offered:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown model '{body.model}'. Choose one of: {', '.join(sorted(offered))}.",
        )
    criteria = TrialFilter(
        material=body.material,
        geometry=GeometryType(body.geometry) if body.geometry else None,
        flow_direction=FlowDirection(body.flow_direction) if body.flow_direction else None,
        include_synthetic=include_synthetic,
    )
    model = body.model if body.model in offered else None
    return ask_out(use_case.execute(AssistantQuery(body.question, criteria, body.metric, model)))
