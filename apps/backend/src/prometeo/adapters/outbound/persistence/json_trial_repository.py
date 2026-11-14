"""TrialRepository backed by a curated JSON file — the MVP data store.

Lets the team ship a verifiable, version-controlled BASS-II sample before Postgres is ready.
"""

from __future__ import annotations

import json
from pathlib import Path

from prometeo.adapters.outbound.persistence.trial_codec import trial_from_json
from prometeo.domain.experiments.filters import TrialFilter
from prometeo.domain.experiments.model import Trial


class JsonTrialRepository:
    def __init__(self, paths: list[Path]) -> None:
        self._trials: dict[str, Trial] = {}
        for path in paths:
            for raw in json.loads(path.read_text(encoding="utf-8")):
                trial = trial_from_json(raw)
                if trial.id in self._trials:
                    raise ValueError(f"Duplicate trial id '{trial.id}' in {path}")
                self._trials[trial.id] = trial

    def get(self, trial_id: str) -> Trial | None:
        return self._trials.get(trial_id)

    def search(self, criteria: TrialFilter) -> list[Trial]:
        return [t for t in self._trials.values() if criteria.matches(t)]

    def list_all(self) -> list[Trial]:
        return list(self._trials.values())
