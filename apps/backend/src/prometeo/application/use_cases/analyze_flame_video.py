"""03 · FlameVision — track the luminous front in a NASA video and derive spread velocity.

The velocity is computed only from a calibrated track that the detector did not reject.
A rejected track (saturation, low coverage, unstable scene…) yields no number: the reason is
returned instead. An uncalibrated video never reaches this use case; analyse it in pixels
with `tools/flamevision/track_video.py`.
"""

from __future__ import annotations

from dataclasses import dataclass

from prometeo.application.ports.outbound import FlameFrontDetector, TrialRepository
from prometeo.domain.flamevision.model import Calibration, FlameFrontTrack, ValidationStatus
from prometeo.domain.physics.metrics import flame_spread_velocity_fit
from prometeo.domain.shared.errors import NotFoundError
from prometeo.domain.shared.quantity import Quantity

# A two-point "fit" has no residuals and hides tracking errors, so ask for more.
MIN_SAMPLES_FOR_FIT = 3


@dataclass(frozen=True, slots=True)
class FlameVisionResult:
    track: FlameFrontTrack
    # Derived from the luminous leading edge. UNVALIDATED until checked against a reference.
    spread_velocity: Quantity | None
    # Why `spread_velocity` is None. None when a velocity was computed.
    withheld_reason: str | None = None


class AnalyzeFlameVideo:
    def __init__(self, trials: TrialRepository, detector: FlameFrontDetector) -> None:
        self._trials = trials
        self._detector = detector

    def execute(self, trial_id: str, video_uri: str, calibration: Calibration) -> FlameVisionResult:
        if self._trials.get(trial_id) is None:
            raise NotFoundError(f"Trial '{trial_id}' not found")
        track = self._detector.track(trial_id, video_uri, calibration)
        if track.validation is ValidationStatus.REJECTED:
            reason = track.validation_note or "track rejected by the detector"
            return FlameVisionResult(track, None, f"Track rejected: {reason}")
        if len(track.samples) < MIN_SAMPLES_FOR_FIT:
            return FlameVisionResult(
                track,
                None,
                f"Only {len(track.samples)} tracked samples; "
                f"at least {MIN_SAMPLES_FOR_FIT} are needed for a velocity fit",
            )
        if len({s.time_s for s in track.samples}) < 2:
            return FlameVisionResult(track, None, "All tracked samples share one timestamp")
        velocity = flame_spread_velocity_fit(
            [Quantity(s.position_mm, "mm") for s in track.samples],
            [Quantity(s.time_s, "s") for s in track.samples],
        )
        return FlameVisionResult(track, velocity)
