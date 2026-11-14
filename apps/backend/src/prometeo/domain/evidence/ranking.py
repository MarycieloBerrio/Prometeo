"""EvidenceRank — rule-based, interpretable evidence classification (MVP).

Three independent dimensions, never collapsed into a fake "confidence %":
  * relevance  — do fuel, geometry, flow and conditions match the question?
  * quality    — is the value measured and traceable to a source and method?
  * coverage   — are there enough results to support the comparison?
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from prometeo.domain.experiments.filters import TrialFilter
from prometeo.domain.experiments.model import DataQuality, Trial


class EvidenceTier(StrEnum):
    DIRECT = "direct"  # directly comparable evidence
    PARTIAL = "partial"  # partially comparable evidence
    INSUFFICIENT = "insufficient"


class Level(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(frozen=True, slots=True)
class EvidenceAssessment:
    trial_id: str
    relevance: Level
    quality: Level
    tier: EvidenceTier
    reasons: tuple[str, ...]


MIN_TRIALS_FOR_COMPARISON = 2


def assess_trial(trial: Trial, query: TrialFilter, metric: str | None) -> EvidenceAssessment:
    reasons: list[str] = []

    relevance = Level.HIGH if query.matches(trial) else Level.LOW
    if relevance is Level.LOW:
        reasons.append("Trial conditions do not match the query")

    measurement = trial.measurement(metric) if metric else None
    if trial.is_synthetic:
        quality = Level.LOW
        reasons.append("Synthetic fixture — not evidence")
    elif metric and measurement is None:
        quality = Level.LOW
        reasons.append(f"No '{metric}' result recorded for this trial")
    elif measurement is not None:
        quality = _quality_of(measurement.quality, measurement.provenance.is_traceable, reasons)
    else:
        quality = Level.MEDIUM if trial.provenance.is_traceable else Level.LOW

    if relevance is Level.HIGH and quality is Level.HIGH:
        tier = EvidenceTier.DIRECT
    elif relevance is Level.HIGH and quality is Level.MEDIUM:
        tier = EvidenceTier.PARTIAL
    else:
        tier = EvidenceTier.INSUFFICIENT
    return EvidenceAssessment(trial.id, relevance, quality, tier, tuple(reasons))


def overall_tier(assessments: list[EvidenceAssessment]) -> EvidenceTier:
    """Coverage rule for *comparative* conclusions: need ≥ `MIN_TRIALS_FOR_COMPARISON`.

    Semantics (unchanged signature for the assistant):
    - `direct` / `partial` / `insufficient` are interpretable tiers — never a confidence %.
    - Requiring two usable trials is appropriate when answering how a response changes
      across conditions. It is **not** a claim that a single well-documented trial is
      scientifically worthless; single-trial descriptive questions need a separate
      interface (see docs/science-validation-daniel.md — handoff to Evidence Assistant).
    """
    usable = [a for a in assessments if a.tier is not EvidenceTier.INSUFFICIENT]
    if len(usable) < MIN_TRIALS_FOR_COMPARISON:
        return EvidenceTier.INSUFFICIENT
    if all(a.tier is EvidenceTier.DIRECT for a in usable):
        return EvidenceTier.DIRECT
    return EvidenceTier.PARTIAL


def _quality_of(q: DataQuality, traceable: bool, reasons: list[str]) -> Level:
    if not traceable:
        reasons.append("Result lacks a traceable source")
        return Level.LOW
    if q is DataQuality.MEASURED:
        return Level.HIGH
    if q is DataQuality.DERIVED:
        reasons.append("Value derived by Prometeo from measured data")
        return Level.MEDIUM
    reasons.append(f"Data quality is '{q}'")
    return Level.LOW
