"""AnalyzeFlameVideo: a velocity only from a usable, calibrated track. No OpenCV needed."""

from __future__ import annotations

import pytest

from prometeo.application.use_cases.analyze_flame_video import AnalyzeFlameVideo
from prometeo.domain.experiments.filters import TrialFilter
from prometeo.domain.experiments.model import Trial
from prometeo.domain.flamevision.model import (
    Calibration,
    FlameFrontTrack,
    FrontSample,
    TrackedFeature,
    ValidationStatus,
)
from prometeo.domain.shared.errors import NotFoundError
from tests.factories import make_trial

CAL = Calibration(mm_per_pixel=0.1, fps=10.0)


class _Trials:
    def get(self, trial_id: str) -> Trial | None:
        return make_trial(trial_id) if trial_id == "T-1" else None

    def search(self, criteria: TrialFilter) -> list[Trial]:
        return []

    def list_all(self) -> list[Trial]:
        return []


class _Detector:
    def __init__(
        self,
        samples: tuple[FrontSample, ...],
        validation: ValidationStatus = ValidationStatus.UNVALIDATED,
        note: str | None = None,
    ) -> None:
        self._samples, self._validation, self._note = samples, validation, note

    def track(self, trial_id: str, video_uri: str, calibration: Calibration) -> FlameFrontTrack:
        return FlameFrontTrack(
            trial_id=trial_id,
            video_uri=video_uri,
            feature=TrackedFeature.LUMINOUS_LEADING_EDGE,
            calibration=calibration,
            samples=self._samples,
            validation=self._validation,
            validation_note=self._note,
        )


def _samples(n: int, mm_per_s: float = 2.0) -> tuple[FrontSample, ...]:
    return tuple(
        FrontSample(frame=i, time_s=i / 10, position_mm=mm_per_s * i / 10) for i in range(n)
    )


def test_velocity_is_fitted_in_mm_per_s_and_stays_unvalidated() -> None:
    result = AnalyzeFlameVideo(_Trials(), _Detector(_samples(20))).execute("T-1", "v.mp4", CAL)

    assert result.spread_velocity is not None
    assert result.spread_velocity.unit == "mm/s"
    assert result.spread_velocity.value == pytest.approx(2.0)
    assert result.withheld_reason is None
    assert result.track.validation is ValidationStatus.UNVALIDATED


def test_rejected_track_yields_no_velocity() -> None:
    detector = _Detector(_samples(20), ValidationStatus.REJECTED, "NOT SUITABLE: saturated")
    result = AnalyzeFlameVideo(_Trials(), detector).execute("T-1", "v.mp4", CAL)

    assert result.spread_velocity is None
    assert result.withheld_reason is not None and "saturated" in result.withheld_reason


@pytest.mark.parametrize("n", [0, 1, 2])
def test_too_few_samples_yield_no_velocity(n: int) -> None:
    result = AnalyzeFlameVideo(_Trials(), _Detector(_samples(n))).execute("T-1", "v.mp4", CAL)

    assert result.spread_velocity is None
    assert result.withheld_reason is not None and "samples" in result.withheld_reason


def test_identical_timestamps_yield_no_velocity() -> None:
    samples = tuple(FrontSample(frame=i, time_s=1.0, position_mm=float(i)) for i in range(4))
    result = AnalyzeFlameVideo(_Trials(), _Detector(samples)).execute("T-1", "v.mp4", CAL)

    assert result.spread_velocity is None
    assert result.withheld_reason == "All tracked samples share one timestamp"


def test_unknown_trial_raises() -> None:
    with pytest.raises(NotFoundError):
        AnalyzeFlameVideo(_Trials(), _Detector(_samples(5))).execute("nope", "v.mp4", CAL)
