"""01 · Experiment Explorer."""

from __future__ import annotations

from prometeo.application.ports.outbound import TrialRepository
from prometeo.domain.experiments.filters import TrialFilter
from prometeo.domain.experiments.model import Trial
from prometeo.domain.shared.errors import NotFoundError


class ExploreExperiments:
    def __init__(self, trials: TrialRepository) -> None:
        self._trials = trials

    def search(self, criteria: TrialFilter) -> list[Trial]:
        return self._trials.search(criteria)

    def get(self, trial_id: str) -> Trial:
        trial = self._trials.get(trial_id)
        if trial is None:
            raise NotFoundError(f"Trial '{trial_id}' not found")
        return trial
