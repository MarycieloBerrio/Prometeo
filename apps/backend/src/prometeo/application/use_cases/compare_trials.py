"""02 · Combustion Comparison Lab."""

from __future__ import annotations

from dataclasses import dataclass

from prometeo.application.ports.outbound import TrialRepository
from prometeo.domain.experiments.model import DataQuality, Measurement, Trial
from prometeo.domain.physics.compatibility import (
    Comparability,
    CompatibilityReport,
    Variable,
    assess_compatibility,
)
from prometeo.domain.shared.errors import DomainError, NotFoundError
from prometeo.domain.shared.quantity import Quantity

PARTIAL_WITHHELD_REASON = (
    "Trials are only partially comparable (unknown or mismatched controlled conditions). "
    "Causal deltas are withheld; inspect each trial's recorded values descriptively. "
    "Do not treat a numeric difference as an isolated effect of the varied variable."
)

NOT_COMPARABLE_WITHHELD_REASON = (
    "Trials differ in controlled variables; deltas withheld."
)

QUALITY_SKIP_REASON = (
    "Metric skipped: evidence deltas require measured or derived (with method) "
    "traceable results; extracted/unavailable/synthetic-vs-real pairs are not subtracted "
    "as scientific effects. Both-SYNTHETIC remains allowed only for development fixtures."
)


@dataclass(frozen=True, slots=True)
class MetricDelta:
    metric: str
    a: Measurement
    b: Measurement
    difference: Quantity  # b - a, in a's unit


@dataclass(frozen=True, slots=True)
class ComparisonResult:
    trials: tuple[Trial, Trial]
    compatibility: CompatibilityReport
    deltas: tuple[MetricDelta, ...]
    withheld_reason: str | None  # set when numbers are withheld because trials aren't comparable


class CompareTrials:
    def __init__(self, trials: TrialRepository) -> None:
        self._trials = trials

    def execute(
        self, trial_a: str, trial_b: str, varied: frozenset[Variable], metrics: list[str]
    ) -> ComparisonResult:
        a, b = self._load(trial_a), self._load(trial_b)
        report = assess_compatibility(a, b, varied)

        if report.level is Comparability.NOT_COMPARABLE:
            return ComparisonResult((a, b), report, (), NOT_COMPARABLE_WITHHELD_REASON)

        # PARTIAL: keep individual trial sheets visible via `trials`, but do not present
        # deltas as controlled causal effects of the varied variable.
        if report.level is Comparability.PARTIAL:
            return ComparisonResult((a, b), report, (), PARTIAL_WITHHELD_REASON)

        deltas: list[MetricDelta] = []
        skipped_quality = False
        skipped_units = False
        for name in metrics:
            ma, mb = a.measurement(name), b.measurement(name)
            if ma is None or mb is None:
                continue
            if not _evidence_delta_allowed(ma, mb):
                skipped_quality = True
                continue
            try:
                diff = mb.value.to(ma.value.unit).value - ma.value.value
            except DomainError:
                skipped_units = True
                continue
            deltas.append(MetricDelta(name, ma, mb, Quantity(diff, ma.value.unit)))

        withheld: str | None = None
        if not deltas and (skipped_quality or skipped_units):
            parts: list[str] = []
            if skipped_quality:
                parts.append(QUALITY_SKIP_REASON)
            if skipped_units:
                parts.append(
                    "Metric skipped: incompatible units between trial results; "
                    "no incorrect numeric difference is invented."
                )
            withheld = " ".join(parts)
        return ComparisonResult((a, b), report, tuple(deltas), withheld)

    def _load(self, trial_id: str) -> Trial:
        t = self._trials.get(trial_id)
        if t is None:
            raise NotFoundError(f"Trial '{trial_id}' not found")
        return t


def _evidence_delta_allowed(ma: Measurement, mb: Measurement) -> bool:
    """Admit only scientifically usable evidence pairs (or both-SYNTHETIC for fixtures).

    Rejected for causal/evidence deltas: EXTRACTED, UNAVAILABLE, mixed SYNTHETIC↔other,
    DERIVED without a recorded method, or untraceable provenance.
    """
    qa, qb = ma.quality, mb.quality

    if qa is DataQuality.SYNTHETIC and qb is DataQuality.SYNTHETIC:
        return True  # development fixtures only — never NASA evidence

    if DataQuality.SYNTHETIC in (qa, qb):
        return False
    if qa in (DataQuality.EXTRACTED, DataQuality.UNAVAILABLE):
        return False
    if qb in (DataQuality.EXTRACTED, DataQuality.UNAVAILABLE):
        return False

    allowed = {DataQuality.MEASURED, DataQuality.DERIVED}
    if qa not in allowed or qb not in allowed:
        return False

    if qa is DataQuality.DERIVED and not (ma.method and ma.method.strip()):
        return False
    if qb is DataQuality.DERIVED and not (mb.method and mb.method.strip()):
        return False

    return ma.provenance.is_traceable and mb.provenance.is_traceable
