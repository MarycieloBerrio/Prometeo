"""04 · Prometeo Research Assistant — the Evidence Engine pipeline.

Order is mandatory:
  1. Evidence Retrieval   (structured trials + documents)
  2. Physics Validator    (compatibility of the retrieved trials)
  3. Scientific Analysis  (deterministic computations only)
  4. Evidence Audit       (EvidenceRank tiers, coverage, limitations)
  5. Explanation          (LLM writes prose ONLY from the audited packet)

If the audit says evidence is insufficient, the engine refuses to extrapolate and never
asks the LLM to invent a value.
"""

from __future__ import annotations

from dataclasses import dataclass

from prometeo.application.ports.outbound import (
    DocumentChunk,
    DocumentRetriever,
    EvidencePacket,
    Explanation,
    ExplanationGenerator,
    TrialRepository,
)
from prometeo.domain.evidence.ranking import (
    EvidenceAssessment,
    EvidenceTier,
    assess_trial,
    overall_tier,
)
from prometeo.domain.experiments.filters import TrialFilter
from prometeo.domain.experiments.model import Trial


@dataclass(frozen=True, slots=True)
class AssistantQuery:
    question: str
    criteria: TrialFilter
    metric: str | None = None  # e.g. "flame_spread_rate"


@dataclass(frozen=True, slots=True)
class AssistantAnswer:
    tier: EvidenceTier
    explanation: Explanation | None  # None when the engine refuses to conclude
    refusal_reason: str | None
    trials: tuple[Trial, ...]
    assessments: tuple[EvidenceAssessment, ...]
    documents: tuple[DocumentChunk, ...]
    computed_facts: tuple[str, ...]
    limitations: tuple[str, ...]


STANDING_LIMITATIONS = (
    "Microgravity results do not transfer directly to partial gravity (Moon, Mars).",
    "Small-sample results do not predict full-scale fires without validation.",
    "Prometeo does not certify materials or predict fire risk.",
)


class AskResearchAssistant:
    def __init__(
        self,
        trials: TrialRepository,
        documents: DocumentRetriever,
        explainer: ExplanationGenerator,
    ) -> None:
        self._trials = trials
        self._documents = documents
        self._explainer = explainer

    def execute(self, query: AssistantQuery) -> AssistantAnswer:
        # 1. Retrieval
        trials = self._trials.search(query.criteria)
        docs = self._documents.retrieve(query.question)

        # 2 + 4. Validation & audit (per-trial relevance/quality, then coverage)
        assessments = [assess_trial(t, query.criteria, query.metric) for t in trials]
        tier = overall_tier(assessments)

        # 3. Deterministic analysis — facts are strings built from recorded values only
        facts = _facts(trials, query.metric)
        limitations = list(STANDING_LIMITATIONS)
        if any(t.investigation is not trials[0].investigation for t in trials[1:]):
            limitations.append("Trials come from different investigations; scales differ.")

        if tier is EvidenceTier.INSUFFICIENT:
            return AssistantAnswer(
                tier=tier,
                explanation=None,
                refusal_reason=(
                    "The available trials do not support a conclusion for these conditions. "
                    "Prometeo will not extrapolate beyond recorded evidence."
                ),
                trials=tuple(trials),
                assessments=tuple(assessments),
                documents=tuple(docs),
                computed_facts=tuple(facts),
                limitations=tuple(limitations),
            )

        # 5. Explanation
        usable = [
            t
            for t, a in zip(trials, assessments, strict=True)
            if a.tier is not EvidenceTier.INSUFFICIENT
        ]
        packet = EvidencePacket(query.question, usable, facts, docs, limitations)
        explanation = self._explainer.explain(packet)
        return AssistantAnswer(
            tier, explanation, None, tuple(trials), tuple(assessments), tuple(docs),
            tuple(facts), tuple(limitations),
        )


def _facts(trials: list[Trial], metric: str | None) -> list[str]:
    out: list[str] = []
    for t in trials:
        conds = (
            f"O2={t.oxygen or 'n/a'}, flow={t.ventilation.speed or 'n/a'} "
            f"({t.ventilation.direction}), fuel={t.fuel.material}, geometry={t.geometry.type}"
        )
        m = t.measurement(metric) if metric else None
        value = f"; {metric}={m.value} [{m.quality}]" if m else ""
        out.append(f"[{t.id}] {conds}{value}")
    return out
