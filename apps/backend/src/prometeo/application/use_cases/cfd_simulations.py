"""CFD Physics Lab queries — numerical simulations linked to experimental trial ids."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from prometeo.domain.cfd.model import CfdSimulation
from prometeo.domain.shared.errors import NotFoundError


class CfdRepository(Protocol):
    def list_all(self) -> list[CfdSimulation]: ...
    def get(self, simulation_id: str) -> CfdSimulation | None: ...
    def for_trial(self, trial_id: str) -> CfdSimulation | None: ...


@dataclass(frozen=True, slots=True)
class CfdFieldSample:
    simulation_id: str
    points: tuple[dict[str, float], ...]
    units: dict[str, str]
    downsample_stride: int
    n_points_source: int
    viewer_note: str | None = None


class ListCfdSimulations:
    def __init__(self, repo: CfdRepository) -> None:
        self._repo = repo

    def execute(self, trial_id: str | None = None) -> list[CfdSimulation]:
        if trial_id:
            sim = self._repo.for_trial(trial_id)
            return [sim] if sim is not None else []
        return self._repo.list_all()


class GetCfdSimulation:
    def __init__(self, repo: CfdRepository, data_dir: Path) -> None:
        self._repo = repo
        self._data_dir = data_dir

    def execute(self, simulation_id: str) -> CfdSimulation:
        sim = self._repo.get(simulation_id)
        if sim is None:
            raise NotFoundError(f"CFD simulation '{simulation_id}' not found")
        return sim

    def field_sample(self, simulation_id: str) -> CfdFieldSample | None:
        sim = self.execute(simulation_id)
        if not sim.field_sample_path:
            return None
        rel = sim.field_sample_path.replace("\\", "/")
        if rel.startswith("data/"):
            rel = rel[len("data/") :]
        path = (self._data_dir / rel).resolve()
        if not path.is_file():
            return None
        raw = json.loads(path.read_text(encoding="utf-8"))
        points = tuple(raw.get("points") or ())
        note = raw.get("viewer_note")
        return CfdFieldSample(
            simulation_id=simulation_id,
            points=points,
            units=dict(raw.get("units") or {}),
            downsample_stride=int(raw.get("downsample_stride") or 1),
            n_points_source=int(raw.get("n_points_source") or len(points)),
            viewer_note=str(note) if note else None,
        )
