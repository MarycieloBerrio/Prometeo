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

MIXED_QUALITY_SKIP_REASON = (
    "Metric skipped: cannot subtract SYNTHETIC and MEASURED (or other mixed-quality) "
    "results as if they were one evidence class."
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
            if not _qualities_commensurable(ma.quality, mb.quality):
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
                parts.append(MIXED_QUALITY_SKIP_REASON)
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


def _qualities_commensurable(qa: DataQuality, qb: DataQuality) -> bool:
    """Allow same-class pairs; reject synthetic↔measured (and similar) as evidence deltas.

    Both-SYNTHETIC is allowed so the development fixture path keeps exercising the engine.
    """
    if qa is qb:
        return True
    synthetic = DataQuality.SYNTHETIC
    if synthetic in (qa, qb) and qa is not qb:
        return False
    # measured↔derived is still a unit conversion of recorded numbers; mark as ok here.
    # EvidenceRank / UI must still show each quality badge.
    return {qa, qb} <= {DataQuality.MEASURED, DataQuality.DERIVED}
