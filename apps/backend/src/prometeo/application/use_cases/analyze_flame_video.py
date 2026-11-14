"""03 · FlameVision — track the luminous front in a NASA video and derive spread velocity."""

from __future__ import annotations

from dataclasses import dataclass

from prometeo.application.ports.outbound import FlameFrontDetector, TrialRepository
from prometeo.domain.flamevision.model import Calibration, FlameFrontTrack
from prometeo.domain.physics.metrics import flame_spread_velocity_fit
from prometeo.domain.shared.errors import NotFoundError
from prometeo.domain.shared.quantity import Quantity


@dataclass(frozen=True, slots=True)
class FlameVisionResult:
    track: FlameFrontTrack
    spread_velocity: Quantity | None  # derived; UNVALIDATED until checked against a reference


class AnalyzeFlameVideo:
    def __init__(self, trials: TrialRepository, detector: FlameFrontDetector) -> None:
        self._trials = trials
        self._detector = detector

    def execute(self, trial_id: str, video_uri: str, calibration: Calibration) -> FlameVisionResult:
        if self._trials.get(trial_id) is None:
            raise NotFoundError(f"Trial '{trial_id}' not found")
        track = self._detector.track(trial_id, video_uri, calibration)
        velocity = None
        if len(track.samples) >= 2:
            velocity = flame_spread_velocity_fit(
                [Quantity(s.position_mm, "mm") for s in track.samples],
                [Quantity(s.time_s, "s") for s in track.samples],
            )
        return FlameVisionResult(track, velocity)
