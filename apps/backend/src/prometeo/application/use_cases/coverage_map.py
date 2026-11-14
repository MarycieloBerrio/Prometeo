"""Evidence coverage map (O2 x ventilation) for the Comparison Lab / Mission Safety Explorer."""

from __future__ import annotations

from collections.abc import Sequence

from prometeo.application.ports.outbound import TrialRepository
from prometeo.domain.evidence.coverage import CoverageMap, build_coverage_map
from prometeo.domain.experiments.filters import TrialFilter

DEFAULT_OXYGEN_EDGES = (0.15, 0.17, 0.19, 0.21, 0.23, 0.25, 0.27, 0.30, 0.35, 0.40)
DEFAULT_FLOW_EDGES_CM_S = (0.0, 1.0, 2.0, 5.0, 10.0, 20.0, 40.0)


class BuildCoverageMap:
    def __init__(self, trials: TrialRepository) -> None:
        self._trials = trials

    def execute(
        self,
        criteria: TrialFilter,
        oxygen_edges: Sequence[float] = DEFAULT_OXYGEN_EDGES,
        flow_edges_cm_s: Sequence[float] = DEFAULT_FLOW_EDGES_CM_S,
    ) -> CoverageMap:
        return build_coverage_map(self._trials.search(criteria), oxygen_edges, flow_edges_cm_s)
