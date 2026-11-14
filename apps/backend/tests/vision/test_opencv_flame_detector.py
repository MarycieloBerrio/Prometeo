"""Software tests for the OpenCV tracker.

All videos are generated in `conftest.py` (a rectangle moving at a known pixel speed). They
are not NASA data and prove nothing about combustion. They check that the code measures what
it is told to measure, and refuses when it cannot.
"""

from __future__ import annotations

import math
from typing import Any

import pytest

from prometeo.adapters.outbound.vision import opencv_flame_detector as module
from prometeo.adapters.outbound.vision.opencv_flame_detector import (
    Axis,
    Direction,
    FrameStatus,
    MaskMode,
    OpenCvFlameDetector,
    Roi,
    SuitabilityLimits,
    TrackerConfig,
    diagnose,
    fit_edge_vs_time,
)
from prometeo.domain.flamevision.model import Calibration, TrackedFeature, ValidationStatus
from prometeo.domain.shared.errors import InvalidMeasurementError

from .conftest import FPS, Scene, VideoFactory

pytest.importorskip("cv2", reason="needs `uv sync --extra vision`")

SPEED_PX_S = 3.0 * FPS  # Scene default: 3 px/frame at 30 fps = 90 px/s
REL_TOL = 0.02  # 2 %: MJPG compression moves the thresholded edge by about a pixel


def test_known_speed_left_to_right_in_pixels(make_video: VideoFactory) -> None:
    track = OpenCvFlameDetector().track_pixels(make_video(Scene()))
    d = diagnose(track)

    assert d.suitable, d.reasons
    assert d.coverage == 1.0
    assert d.fit is not None
    assert d.fit.slope_px_per_s == pytest.approx(SPEED_PX_S, rel=REL_TOL)
    assert d.advance_px_per_s == pytest.approx(SPEED_PX_S, rel=REL_TOL)
    assert d.fit.rms_residual_px < 1.5
    assert d.monotonic_fraction == 1.0
    # Leading edge = right side of the rectangle: x0 + width - 1 at frame 0.
    assert track.observations[0].edge_px == pytest.approx(59, abs=2)


def test_right_to_left_tracks_the_left_edge(make_video: VideoFactory) -> None:
    video = make_video(Scene(x0=260, vx=-3.0))
    detector = OpenCvFlameDetector(config=TrackerConfig(direction=Direction.DECREASING))
    track = detector.track_pixels(video)
    d = diagnose(track)

    assert d.suitable, d.reasons
    assert d.fit is not None
    assert d.fit.slope_px_per_s == pytest.approx(-SPEED_PX_S, rel=REL_TOL)  # image coords
    assert d.advance_px_per_s == pytest.approx(SPEED_PX_S, rel=REL_TOL)  # along direction
    assert track.observations[0].edge_px == pytest.approx(260, abs=2)  # left side


def test_wrong_direction_is_flagged_not_hidden(make_video: VideoFactory) -> None:
    video = make_video(Scene(x0=260, vx=-3.0))
    d = diagnose(OpenCvFlameDetector().track_pixels(video))  # default: increasing

    assert d.advance_px_per_s is not None and d.advance_px_per_s < 0
    assert any("opposite to the configured direction" in w for w in d.warnings)


def test_vertical_motion_with_axis_y(make_video: VideoFactory) -> None:
    video = make_video(Scene(frames=30, x0=150, y0=10, vx=0.0, vy=2.0))
    track = OpenCvFlameDetector(config=TrackerConfig(axis=Axis.Y)).track_pixels(video)
    d = diagnose(track)

    assert d.advance_px_per_s == pytest.approx(2.0 * FPS, rel=REL_TOL)
    assert track.observations[0].edge_px == pytest.approx(10 + 14 - 1, abs=2)


def test_fixed_glare_wins_without_roi_and_loses_with_roi(make_video: VideoFactory) -> None:
    # A large, fixed bright patch plus a smaller moving object.
    video = make_video(Scene(y0=80, glare=(120, 5, 70, 45)))

    naive = diagnose(OpenCvFlameDetector().track_pixels(video))
    assert naive.advance_px_per_s == pytest.approx(0.0, abs=1.0)  # it follows the glare

    roi = Roi(0, 70, 320, 40)  # the strip where the object moves; glare is outside
    track = OpenCvFlameDetector(config=TrackerConfig(roi=roi)).track_pixels(video)
    d = diagnose(track)
    assert d.suitable, d.reasons
    assert d.advance_px_per_s == pytest.approx(SPEED_PX_S, rel=REL_TOL)
    assert all(o.bbox is not None and o.bbox[1] >= 70 for o in track.detections)


def test_larger_reflection_appearing_later_does_not_steal_the_track(
    make_video: VideoFactory,
) -> None:
    # The reflection is bigger than the object and inside the analysed area, but appears
    # after tracking started: continuity must beat size.
    video = make_video(Scene(y0=90, glare=(200, 5, 60, 40), glare_from_frame=20))
    track = OpenCvFlameDetector().track_pixels(video)
    d = diagnose(track)

    assert d.advance_px_per_s == pytest.approx(SPEED_PX_S, rel=REL_TOL)
    assert max(o.candidates for o in track.observations) == 2


def test_region_filling_the_roi_is_not_a_flame(make_video: VideoFactory) -> None:
    video = make_video(Scene(frames=20, glare=(0, 0, 320, 120)))  # whole frame lit
    d = diagnose(OpenCvFlameDetector().track_pixels(video))

    assert d.detected == 0
    assert not d.suitable


def test_occlusion_gap_is_counted_not_crashed(make_video: VideoFactory) -> None:
    video = make_video(Scene(hidden=frozenset(range(20, 30))))
    track = OpenCvFlameDetector().track_pixels(video)

    assert len(track.observations) == 60  # every analysed frame is reported
    assert [o.status for o in track.observations[20:30]] == [FrameStatus.NO_DETECTION] * 10

    strict = diagnose(track, SuitabilityLimits(min_coverage=0.9))
    assert strict.coverage == pytest.approx(50 / 60)
    assert strict.no_detection == 10
    assert strict.longest_gap_frames == 10
    assert not strict.suitable
    assert any("coverage" in r for r in strict.reasons)

    lenient = diagnose(track, SuitabilityLimits(min_coverage=0.8))
    assert lenient.suitable
    assert lenient.advance_px_per_s == pytest.approx(SPEED_PX_S, rel=REL_TOL)


def test_intermittent_flame_keeps_measurable_coverage(make_video: VideoFactory) -> None:
    video = make_video(Scene(hidden=frozenset(range(0, 60, 3))))  # every third frame dark
    d = diagnose(OpenCvFlameDetector().track_pixels(video))

    assert d.coverage == pytest.approx(40 / 60)
    assert d.longest_gap_frames == 1
    assert not d.suitable  # below the default 80 % coverage


def test_dark_video_has_no_detections_and_is_rejected(make_video: VideoFactory) -> None:
    video = make_video(Scene(frames=15, hidden=frozenset(range(15))))
    detector = OpenCvFlameDetector()

    d = diagnose(detector.track_pixels(video))
    assert d.detected == 0 and d.fit is None and d.advance_px_per_s is None
    assert not d.suitable

    track = detector.track("T-1", video, Calibration(mm_per_pixel=0.1, fps=FPS))
    assert track.samples == ()
    assert track.validation is ValidationStatus.REJECTED
    assert track.validation_note is not None and "NOT SUITABLE" in track.validation_note


def test_saturated_object_is_not_suitable(make_video: VideoFactory) -> None:
    d = diagnose(OpenCvFlameDetector().track_pixels(make_video(Scene(level=255))))

    assert d.median_saturated_fraction is not None and d.median_saturated_fraction > 0.5
    assert not d.suitable
    assert any("saturated" in r for r in d.reasons)


def test_camera_motion_outside_roi_is_not_suitable(make_video: VideoFactory) -> None:
    video = make_video(Scene(moving_background=True))
    config = TrackerConfig(roi=Roi(0, 40, 320, 40))
    d = diagnose(OpenCvFlameDetector(config=config).track_pixels(video))

    assert d.background_change_p95 is not None and d.background_change_p95 > 8.0
    assert not d.suitable
    assert any("camera motion" in r for r in d.reasons)


def test_camera_stability_not_assessed_without_roi(make_video: VideoFactory) -> None:
    d = diagnose(OpenCvFlameDetector().track_pixels(make_video(Scene(frames=10))))

    assert d.background_change_p95 is None
    assert any("camera stability was not assessed" in w for w in d.warnings)


def test_spurious_jump_is_recorded_and_excluded(make_video: VideoFactory) -> None:
    video = make_video(Scene(teleport={30: 280.0}))  # one frame far from the trajectory
    config = TrackerConfig(max_jump_px_per_frame=10.0)
    track = OpenCvFlameDetector(config=config).track_pixels(video)
    d = diagnose(track)

    jump = track.observations[30]
    assert jump.status is FrameStatus.SPURIOUS_JUMP
    assert jump.edge_px is not None  # kept for inspection
    assert d.spurious_jumps == 1
    assert d.detected == 59
    assert d.advance_px_per_s == pytest.approx(SPEED_PX_S, rel=REL_TOL)
    assert track.observations[31].status is FrameStatus.DETECTED  # tracking resumes


def test_time_window_and_frame_step(make_video: VideoFactory) -> None:
    config = TrackerConfig(start_s=0.5, end_s=1.5, frame_step=3)
    track = OpenCvFlameDetector(config=config).track_pixels(make_video(Scene()))

    frames = [o.frame for o in track.observations]
    assert frames == list(range(15, 46, 3))
    assert track.frames_decoded == 60
    assert diagnose(track).advance_px_per_s == pytest.approx(SPEED_PX_S, rel=REL_TOL)


def test_color_mask_selects_by_hue(make_video: VideoFactory) -> None:
    # The gray rectangle has no saturation, so a saturated-colour mask must find nothing.
    config = TrackerConfig(
        mask_mode=MaskMode.COLOR_HSV, hsv_lower=(0, 120, 120), hsv_upper=(20, 255, 255)
    )
    d = diagnose(OpenCvFlameDetector(config=config).track_pixels(make_video(Scene(frames=10))))
    assert d.detected == 0

    gray_ok = TrackerConfig(
        mask_mode=MaskMode.COLOR_HSV, hsv_lower=(0, 0, 200), hsv_upper=(179, 40, 255)
    )
    d = diagnose(OpenCvFlameDetector(config=gray_ok).track_pixels(make_video(Scene())))
    assert d.advance_px_per_s == pytest.approx(SPEED_PX_S, rel=REL_TOL)


def test_output_metadata_records_method_and_parameters(make_video: VideoFactory) -> None:
    import cv2

    config = TrackerConfig(threshold=180, roi=Roi(0, 30, 320, 60), blur_kernel_px=3)
    track = OpenCvFlameDetector(config=config).track_pixels(make_video(Scene(frames=10)))

    assert track.config == config
    assert track.feature is TrackedFeature.LUMINOUS_LEADING_EDGE
    assert track.opencv_version == cv2.__version__
    assert (track.frame_width, track.frame_height) == (320, 120)
    assert track.container_fps == pytest.approx(FPS)
    assert track.fps_used == pytest.approx(FPS) and track.fps_source == "container"


def test_calibrated_track_converts_pixels_with_the_given_scale(make_video: VideoFactory) -> None:
    calibration = Calibration(mm_per_pixel=0.1, fps=FPS, origin_px=59.0)
    track = OpenCvFlameDetector().track("T-1", make_video(Scene()), calibration)

    assert track.validation is ValidationStatus.UNVALIDATED  # never validated by itself
    assert track.feature is TrackedFeature.LUMINOUS_LEADING_EDGE
    assert len(track.samples) == 60
    first, last = track.samples[0], track.samples[-1]
    assert first.position_mm == pytest.approx(0.0, abs=0.2)
    velocity_mm_s = (last.position_mm - first.position_mm) / (last.time_s - first.time_s)
    assert velocity_mm_s == pytest.approx(SPEED_PX_S * 0.1, rel=REL_TOL)  # 9 mm/s


def test_calibrated_position_increases_for_right_to_left_flame(make_video: VideoFactory) -> None:
    detector = OpenCvFlameDetector(config=TrackerConfig(direction=Direction.DECREASING))
    calibration = Calibration(mm_per_pixel=0.1, fps=FPS, origin_px=260.0)
    track = detector.track("T-1", make_video(Scene(x0=260, vx=-3.0)), calibration)

    assert track.samples[-1].position_mm > track.samples[0].position_mm


def test_fps_mismatch_between_calibration_and_file_is_reported(make_video: VideoFactory) -> None:
    track = OpenCvFlameDetector().track(
        "T-1", make_video(Scene(frames=10)), Calibration(mm_per_pixel=0.1, fps=60.0)
    )
    assert track.validation_note is not None
    assert "differs from the container fps" in track.validation_note


def test_legacy_constructor_arguments_still_work(make_video: VideoFactory) -> None:
    detector = OpenCvFlameDetector(threshold=180, min_area_px=10, frame_step=2)
    assert detector.config.threshold == 180
    assert detector.config.min_area_px == 10
    assert len(detector.track_pixels(make_video(Scene(frames=10))).observations) == 5


# -- errors: clear failure instead of a number ---------------------------------------------


def test_missing_video_raises() -> None:
    with pytest.raises(FileNotFoundError, match="Cannot open video"):
        OpenCvFlameDetector().track_pixels("does-not-exist.mp4")
    with pytest.raises(FileNotFoundError):
        OpenCvFlameDetector().track("T-1", "does-not-exist.mp4", Calibration(0.1, 30.0))


@pytest.mark.parametrize("fps", [0.0, -30.0, math.nan, math.inf])
def test_invalid_fps_override_raises(make_video: VideoFactory, fps: float) -> None:
    with pytest.raises(InvalidMeasurementError, match="fps_override"):
        OpenCvFlameDetector().track_pixels(make_video(Scene(frames=5)), fps_override=fps)


@pytest.mark.parametrize("reported", [0.0, math.nan])
def test_invalid_container_fps_raises_unless_overridden(
    make_video: VideoFactory, monkeypatch: pytest.MonkeyPatch, reported: float
) -> None:
    import cv2 as real_cv2

    class BrokenFpsCapture:
        def __init__(self, uri: str) -> None:
            self._cap = real_cv2.VideoCapture(uri)

        def get(self, prop: int) -> float:
            return reported if prop == real_cv2.CAP_PROP_FPS else float(self._cap.get(prop))

        def __getattr__(self, name: str) -> Any:
            return getattr(self._cap, name)

    class Cv2WithBrokenFps:
        VideoCapture = BrokenFpsCapture

        def __getattr__(self, name: str) -> Any:
            return getattr(real_cv2, name)

    monkeypatch.setattr(module, "_load_cv2", lambda: Cv2WithBrokenFps())
    video = make_video(Scene(frames=10))

    with pytest.raises(InvalidMeasurementError, match="invalid frame rate"):
        OpenCvFlameDetector().track_pixels(video)

    track = OpenCvFlameDetector().track_pixels(video, fps_override=25.0)
    assert track.container_fps is None
    assert track.fps_used == 25.0 and track.fps_source == "override"


def test_invalid_calibration_is_rejected_by_the_domain() -> None:
    with pytest.raises(InvalidMeasurementError):
        Calibration(mm_per_pixel=0.0, fps=30.0)
    with pytest.raises(InvalidMeasurementError):
        Calibration(mm_per_pixel=0.1, fps=0.0)


def test_roi_outside_frame_raises(make_video: VideoFactory) -> None:
    config = TrackerConfig(roi=Roi(500, 0, 50, 50))
    with pytest.raises(InvalidMeasurementError, match="outside"):
        OpenCvFlameDetector(config=config).track_pixels(make_video(Scene(frames=5)))


@pytest.mark.parametrize(
    "kwargs",
    [
        {"threshold": 300},
        {"mask_mode": MaskMode.COLOR_HSV},
        {"min_area_px": 0},
        {"max_area_fraction": 0.0},
        {"blur_kernel_px": 4},
        {"frame_step": 0},
        {"max_jump_px_per_frame": 0.0},
        {"start_s": 2.0, "end_s": 1.0},
    ],
)
def test_invalid_config_raises(kwargs: dict[str, Any]) -> None:
    with pytest.raises(InvalidMeasurementError):
        TrackerConfig(**kwargs)


def test_invalid_roi_raises() -> None:
    with pytest.raises(InvalidMeasurementError):
        Roi(0, 0, 0, 10)


def test_fit_needs_three_detections() -> None:
    assert fit_edge_vs_time([]) is None
