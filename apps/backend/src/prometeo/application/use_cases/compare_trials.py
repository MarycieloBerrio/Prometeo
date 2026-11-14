"""02 · Combustion Comparison Lab."""

from __future__ import annotations

from dataclasses import dataclass

from prometeo.application.ports.outbound import TrialRepository
from prometeo.domain.experiments.model import Measurement, Trial
from prometeo.domain.physics.compatibility import (
    Comparability,
    CompatibilityReport,
    Variable,
    assess_compatibility,
)
from prometeo.domain.shared.errors import DomainError, NotFoundError
from prometeo.domain.shared.quantity import Quantity


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
            return ComparisonResult(
                (a, b), report, (), "Trials differ in controlled variables; deltas withheld."
            )

        deltas: list[MetricDelta] = []
        for name in metrics:
            ma, mb = a.measurement(name), b.measurement(name)
            if ma is None or mb is None:
                continue
            try:
                diff = mb.value.to(ma.value.unit).value - ma.value.value
            except DomainError:
                continue
            deltas.append(MetricDelta(name, ma, mb, Quantity(diff, ma.value.unit)))
        return ComparisonResult((a, b), report, tuple(deltas), None)

    def _load(self, trial_id: str) -> Trial:
        t = self._trials.get(trial_id)
        if t is None:
            raise NotFoundError(f"Trial '{trial_id}' not found")
        return t
