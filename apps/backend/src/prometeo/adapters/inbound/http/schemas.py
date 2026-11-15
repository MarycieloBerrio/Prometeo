"""HTTP DTOs (pydantic) and domain -> DTO mappers. These shapes are the public API contract
consumed by the frontend through `packages/contracts` (generated from OpenAPI)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from pydantic import BaseModel, Field

from prometeo.application.ports.outbound import DocumentChunk, ExplainerModel
from prometeo.application.use_cases.ask_research_assistant import (
    RELATED_INVESTIGATION,
    SAME_INVESTIGATION,
    AssistantAnswer,
    document_relation,
)
from prometeo.application.use_cases.compare_trials import ComparisonResult
from prometeo.domain.evidence.coverage import CoverageMap
from prometeo.domain.experiments.model import Measurement, Provenance, Trial
from prometeo.domain.physics.compatibility import Variable
from prometeo.domain.shared.quantity import Quantity


class QuantityOut(BaseModel):
    value: float
    unit: str


class ProvenanceOut(BaseModel):
    reference: str
    source_file: str | None = None
    doi: str | None = None
    url: str | None = None
    page: str | None = None
    version: str | None = None


class MeasurementOut(BaseModel):
    name: str
    value: QuantityOut
    quality: str
    uncertainty: QuantityOut | None
    method: str | None
    provenance: ProvenanceOut


class MediaOut(BaseModel):
    kind: str
    uri: str
    start_s: float | None
    end_s: float | None


class TrialOut(BaseModel):
    id: str
    investigation: str
    sample_id: str | None
    material: str
    composition: str | None
    geometry: str
    thickness: QuantityOut | None
    thermal_regime: str
    oxygen: QuantityOut | None
    flow_speed: QuantityOut | None
    flow_direction: str
    pressure: QuantityOut | None
    phenomena: list[str]
    results: list[MeasurementOut]
    media: list[MediaOut]
    provenance: ProvenanceOut
    is_synthetic: bool
    notes: str | None


class CompareRequest(BaseModel):
    trial_a: str
    trial_b: str
    varied: list[Variable] = Field(min_length=1)
    metrics: list[str] = ["flame_spread_rate"]


class IssueOut(BaseModel):
    variable: str
    severity: str
    message: str


class DeltaOut(BaseModel):
    metric: str
    a: MeasurementOut
    b: MeasurementOut
    difference: QuantityOut


class CompareResponse(BaseModel):
    trials: list[TrialOut]
    level: str
    varied: list[str]
    issues: list[IssueOut]
    deltas: list[DeltaOut]
    withheld_reason: str | None


class CoverageCellOut(BaseModel):
    oxygen_range: tuple[float, float]
    flow_range_cm_s: tuple[float, float]
    trial_ids: list[str]
    observed: list[str]
    has_evidence: bool


class CoverageResponse(BaseModel):
    oxygen_edges: list[float]
    flow_edges_cm_s: list[float]
    cells: list[CoverageCellOut]
    unplaced_trial_ids: list[str]


class AskRequest(BaseModel):
    question: str = Field(min_length=3)
    material: str | None = None
    geometry: str | None = None
    flow_direction: str | None = None
    metric: str | None = "flame_spread_rate"
    model: str | None = Field(
        default=None,
        description=(
            "Explanation model for this question, one of GET /assistant/models. Omit for the "
            "default. Ignored when no language model is configured."
        ),
    )


class AssistantModelOut(BaseModel):
    id: str
    label: str
    description: str


class AssistantModelsResponse(BaseModel):
    default: str | None = Field(
        description="Model used when a question names none; null when no model is configured."
    )
    models: list[AssistantModelOut] = Field(
        description="Models a question may pick. Empty with the deterministic explainer."
    )


class AssessmentOut(BaseModel):
    trial_id: str
    relevance: str
    quality: str
    tier: str
    reasons: list[str]
    in_interpretation: bool = Field(
        description=(
            "True when this trial's facts were given to the interpretation (it belongs to a "
            "comparable set). False on a refusal, and for a usable trial that had no "
            "comparable counterpart: `tier` rates the trial alone, not its use in the answer."
        )
    )


class DocumentOut(BaseModel):
    id: str
    excerpt: str = Field(
        description=(
            "Full text of the retrieved chunk, exactly as given to the explanation model, so "
            "every statement attributed to a document can be checked against it."
        )
    )
    score: float
    provenance: ProvenanceOut
    investigation: str | None = Field(
        default=None, description="Investigation the document belongs to, when recorded."
    )
    relation: Literal["same", "related", "other"] = Field(
        description=(
            "How that investigation relates to the usable trials: the same one, one the "
            "catalog lists as related, or another (general background)."
        )
    )
    cited_passages: list[str] = Field(
        description=(
            "Passages of this excerpt quoted by the interpretation, verbatim (whitespace "
            "collapsed). Empty when the interpretation does not quote it."
        )
    )


class AskResponse(BaseModel):
    tier: str
    answer: str | None
    refusal_reason: str | None
    model: str | None
    cited_sources: list[str]
    computed_facts: list[str]
    limitations: list[str]
    assessments: list[AssessmentOut]
    documents: list[DocumentOut]


# ---- mappers --------------------------------------------------------------------------------


def q_out(q: Quantity | None) -> QuantityOut | None:
    return None if q is None else QuantityOut(value=q.value, unit=q.unit)


def prov_out(p: Provenance) -> ProvenanceOut:
    return ProvenanceOut(
        reference=p.reference, source_file=p.source_file, doi=p.doi, url=p.url,
        page=p.page, version=p.version,
    )


def measurement_out(m: Measurement) -> MeasurementOut:
    return MeasurementOut(
        name=m.name,
        value=QuantityOut(value=m.value.value, unit=m.value.unit),
        quality=m.quality.value,
        uncertainty=q_out(m.uncertainty),
        method=m.method,
        provenance=prov_out(m.provenance),
    )


def trial_out(t: Trial) -> TrialOut:
    return TrialOut(
        id=t.id,
        investigation=t.investigation.value,
        sample_id=t.sample_id,
        material=t.fuel.material,
        composition=t.fuel.composition,
        geometry=t.geometry.type.value,
        thickness=q_out(t.geometry.thickness),
        thermal_regime=t.geometry.thermal_regime.value,
        oxygen=q_out(t.oxygen),
        flow_speed=q_out(t.ventilation.speed),
        flow_direction=t.ventilation.direction.value,
        pressure=q_out(t.pressure),
        phenomena=sorted(p.value for p in t.phenomena),
        results=[measurement_out(m) for m in t.results],
        media=[MediaOut(kind=m.kind, uri=m.uri, start_s=m.start_s, end_s=m.end_s) for m in t.media],
        provenance=prov_out(t.provenance),
        is_synthetic=t.is_synthetic,
        notes=t.notes,
    )


def compare_out(r: ComparisonResult) -> CompareResponse:
    return CompareResponse(
        trials=[trial_out(t) for t in r.trials],
        level=r.compatibility.level.value,
        varied=sorted(v.value for v in r.compatibility.varied),
        issues=[
            IssueOut(variable=i.variable.value, severity=i.severity.value, message=i.message)
            for i in r.compatibility.issues
        ],
        deltas=[
            DeltaOut(
                metric=d.metric,
                a=measurement_out(d.a),
                b=measurement_out(d.b),
                difference=QuantityOut(value=d.difference.value, unit=d.difference.unit),
            )
            for d in r.deltas
        ],
        withheld_reason=r.withheld_reason,
    )


def coverage_out(c: CoverageMap) -> CoverageResponse:
    return CoverageResponse(
        oxygen_edges=list(c.oxygen_edges),
        flow_edges_cm_s=list(c.flow_edges),
        cells=[
            CoverageCellOut(
                oxygen_range=cell.oxygen_range,
                flow_range_cm_s=cell.flow_range,
                trial_ids=list(cell.trial_ids),
                observed=sorted(p.value for p in cell.observed),
                has_evidence=cell.has_evidence,
            )
            for cell in c.cells
        ],
        unplaced_trial_ids=list(c.unplaced_trial_ids),
    )


class CfdSimulationOut(BaseModel):
    simulation_id: str
    reference_trial_id: str
    result_kind: str
    solver: str
    solver_version: str
    model_type: str
    inlet_velocity_m_s: float
    inlet_velocity_cm_s: float
    oxygen_context_percent: float | None
    mesh_cell_count: int | None
    residuals: dict[str, float]
    mass_balance_error: float | None
    mass_balance_status: str
    mesh_independence: str
    convergence_status: str
    validation_status: str
    has_field_sample: bool
    geometry_assumptions: list[str]
    limitations: list[str]
    solver_announced_convergence: bool = False
    convergence_evidence: str = ""
    mesh_quality_status: str = "not_verified"
    continuity_global_abs: float | None = None


class CfdFieldPointOut(BaseModel):
    x: float
    y: float
    z: float
    u_mag: float
    p: float
    ux: float | None = None
    uy: float | None = None
    uz: float | None = None


class CfdFieldSampleOut(BaseModel):
    simulation_id: str
    units: dict[str, str]
    downsample_stride: int
    n_points_source: int
    points: list[CfdFieldPointOut]
    viewer_note: str | None = None


class CfdInterpretationOut(BaseModel):
    question: str
    nasa_measured: list[str]
    simulation_computed: list[str]
    literature_mechanisms: list[str]
    cannot_conclude: list[str]
    sources: list[str]


def cfd_out(s: object) -> CfdSimulationOut:
    from prometeo.domain.cfd.model import CfdSimulation

    assert isinstance(s, CfdSimulation)
    return CfdSimulationOut(
        simulation_id=s.simulation_id,
        reference_trial_id=s.reference_trial_id,
        result_kind=s.result_kind,
        solver=s.solver,
        solver_version=s.solver_version,
        model_type=s.model_type,
        inlet_velocity_m_s=s.inlet_velocity_m_s,
        inlet_velocity_cm_s=s.inlet_velocity_cm_s,
        oxygen_context_percent=s.oxygen_context_percent,
        mesh_cell_count=s.mesh_cell_count,
        residuals=dict(s.residuals),
        mass_balance_error=s.mass_balance_error,
        mass_balance_status=s.mass_balance_status,
        mesh_independence=s.mesh_independence,
        convergence_status=s.convergence_status.value,
        validation_status=s.validation_status.value,
        has_field_sample=bool(s.field_sample_path),
        geometry_assumptions=list(s.geometry_assumptions),
        limitations=list(s.limitations),
        solver_announced_convergence=s.solver_announced_convergence,
        convergence_evidence=s.convergence_evidence,
        mesh_quality_status=s.mesh_quality_status,
        continuity_global_abs=s.continuity_global_abs,
    )


def _relation(
    doc: DocumentChunk, investigations: frozenset[str]
) -> Literal["same", "related", "other"]:
    relation = document_relation(doc, investigations)
    if relation == SAME_INVESTIGATION:
        return "same"
    return "related" if relation == RELATED_INVESTIGATION else "other"


def models_out(models: Sequence[ExplainerModel]) -> AssistantModelsResponse:
    return AssistantModelsResponse(
        default=models[0].id if models else None,
        models=[
            AssistantModelOut(id=m.id, label=m.label, description=m.description) for m in models
        ],
    )


def ask_out(a: AssistantAnswer) -> AskResponse:
    return AskResponse(
        tier=a.tier.value,
        answer=a.explanation.text if a.explanation else None,
        refusal_reason=a.refusal_reason,
        model=a.explanation.model if a.explanation else None,
        cited_sources=list(a.explanation.cited_sources) if a.explanation else [],
        computed_facts=list(a.computed_facts),
        limitations=list(a.limitations),
        assessments=[
            AssessmentOut(
                trial_id=x.trial_id, relevance=x.relevance.value, quality=x.quality.value,
                tier=x.tier.value, reasons=list(x.reasons),
                in_interpretation=x.trial_id in a.interpreted_trial_ids,
            )
            for x in a.assessments
        ],
        documents=[
            DocumentOut(
                id=d.id,
                excerpt=d.text,
                score=d.score,
                provenance=prov_out(d.provenance),
                investigation=d.investigation,
                relation=_relation(d, a.evidence_investigations),
                cited_passages=[c.cited_text for c in a.citations if c.chunk_id == d.id],
            )
            for d in a.documents
        ],
    )
