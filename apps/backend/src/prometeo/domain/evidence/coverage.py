"""Evidence coverage map: O2 concentration x ventilation speed.

Distinguishes *absence of measurements* from *absence of combustion*:
an empty cell means "no evidence recorded", never "safe".
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

from prometeo.domain.experiments.model import Phenomenon, Trial


@dataclass(frozen=True, slots=True)
class CoverageCell:
    oxygen_range: tuple[float, float]  # fraction 0..1
    flow_range: tuple[float, float]  # cm/s
    trial_ids: tuple[str, ...] = ()
    observed: frozenset[Phenomenon] = field(default_factory=frozenset)

    @property
    def has_evidence(self) -> bool:
        return bool(self.trial_ids)


@dataclass(frozen=True, slots=True)
class CoverageMap:
    oxygen_edges: tuple[float, ...]
    flow_edges: tuple[float, ...]
    cells: tuple[CoverageCell, ...]
    unplaced_trial_ids: tuple[str, ...]  # trials lacking O2 or flow values


def build_coverage_map(
    trials: Iterable[Trial],
    oxygen_edges: Sequence[float],
    flow_edges_cm_s: Sequence[float],
) -> CoverageMap:
    if len(oxygen_edges) < 2 or len(flow_edges_cm_s) < 2:
        raise ValueError("Need at least two edges per axis")

    buckets: dict[tuple[int, int], list[Trial]] = {}
    unplaced: list[str] = []
    for t in trials:
        if t.oxygen is None or t.ventilation.speed is None:
            unplaced.append(t.id)
            continue
        o2 = t.oxygen.to("fraction").value
        flow = t.ventilation.speed.to("cm/s").value
        i, j = _bin(o2, oxygen_edges), _bin(flow, flow_edges_cm_s)
        if i is None or j is None:
            unplaced.append(t.id)
            continue
        buckets.setdefault((i, j), []).append(t)

    cells = []
    for i in range(len(oxygen_edges) - 1):
        for j in range(len(flow_edges_cm_s) - 1):
            ts = buckets.get((i, j), [])
            cells.append(
                CoverageCell(
                    oxygen_range=(oxygen_edges[i], oxygen_edges[i + 1]),
                    flow_range=(flow_edges_cm_s[j], flow_edges_cm_s[j + 1]),
                    trial_ids=tuple(t.id for t in ts),
                    observed=frozenset(p for t in ts for p in t.phenomena),
                )
            )
    return CoverageMap(tuple(oxygen_edges), tuple(flow_edges_cm_s), tuple(cells), tuple(unplaced))


def _bin(x: float, edges: Sequence[float]) -> int | None:
    for k in range(len(edges) - 1):
        last = k == len(edges) - 2
        if edges[k] <= x < edges[k + 1] or (last and x == edges[k + 1]):
            return k
    return None
