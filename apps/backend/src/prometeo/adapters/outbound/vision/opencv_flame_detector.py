"""FlameFrontDetector using OpenCV (requires the `vision` extra).

What is measured
----------------
The LUMINOUS LEADING EDGE: the outermost pixel, along one image axis, of the bright connected
region selected as "the flame". This is NOT the reaction front, the pyrolysis front, a
temperature or a heat-release rate. Results stay UNVALIDATED until compared with a reference.

Two entry points
----------------
* ``track_pixels``: uncalibrated analysis. Positions are in pixels, rates in pixels/second.
  Use this when no verifiable mm/pixel scale exists. It never emits millimetres.
* ``track``: the ``FlameFrontDetector`` port. Needs a real ``Calibration``. A video that fails
  the suitability checks comes back with ``validation = rejected`` and the reasons in
  ``validation_note`` instead of a misleading track.

Every analysed frame is kept as a ``FrameObservation`` (detected, no detection or spurious
jump). Nothing is dropped silently, so coverage and gaps can be audited.
"""

from __future__ import annotations

import importlib
import itertools
import math
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from prometeo.domain.flamevision.model import (
    Calibration,
    FlameFrontTrack,
    FrontSample,
    TrackedFeature,
    ValidationStatus,
)
from prometeo.domain.shared.errors import InvalidMeasurementError

_MAX_PLAUSIBLE_FPS = 100_000.0


class Axis(StrEnum):
    X = "x"
    Y = "y"


class Direction(StrEnum):
    """Which way the flame advances along the axis, in image coordinates."""

    INCREASING = "increasing"  # towards larger x (right) or larger y (down)
    DECREASING = "decreasing"  # towards smaller x (left) or smaller y (up)


class MaskMode(StrEnum):
    LUMINANCE = "luminance"  # gray level >= threshold
    COLOR_HSV = "color_hsv"  # pixel inside [hsv_lower, hsv_upper] (OpenCV HSV ranges)


class FrameStatus(StrEnum):
    DETECTED = "detected"
    NO_DETECTION = "no_detection"
    SPURIOUS_JUMP = "spurious_jump"  # a region was found but it moved implausibly far


@dataclass(frozen=True, slots=True)
class Roi:
    """Region of interest in full-frame pixel coordinates (top-left origin)."""

    x: int
    y: int
    width: int
    height: int

    def __post_init__(self) -> None:
        if self.x < 0 or self.y < 0 or self.width <= 0 or self.height <= 0:
            raise InvalidMeasurementError(
                "ROI needs x >= 0, y >= 0 and positive width and height (pixels)"
            )


@dataclass(frozen=True, slots=True)
class TrackerConfig:
    """Every parameter that changes the result. Exported verbatim with each track."""

    threshold: int = 200  # gray level 0..255, used by MaskMode.LUMINANCE
    mask_mode: MaskMode = MaskMode.LUMINANCE
    hsv_lower: tuple[int, int, int] | None = None
    hsv_upper: tuple[int, int, int] | None = None
    roi: Roi | None = None
    axis: Axis = Axis.X
    direction: Direction = Direction.INCREASING
    min_area_px: int = 25
    # A region covering more than this fraction of the ROI is treated as glare or scene
    # illumination, not a flame, and is ignored.
    max_area_fraction: float = 0.5
    blur_kernel_px: int = 0  # Gaussian blur before masking; 0 disables, otherwise odd
    open_kernel_px: int = 3  # morphological opening to remove specks; 0 disables
    frame_step: int = 1
    start_s: float | None = None
    end_s: float | None = None
    # Largest plausible edge displacement between consecutive video frames. None disables
    # the check. A larger displacement is recorded as SPURIOUS_JUMP, never used as a sample.
    max_jump_px_per_frame: float | None = None
    saturation_level: int = 250  # gray level counted as sensor saturation

    def __post_init__(self) -> None:
        if not 0 <= self.threshold <= 255:
            raise InvalidMeasurementError("threshold must be a gray level in 0..255")
        if self.mask_mode is MaskMode.COLOR_HSV and (
            self.hsv_lower is None or self.hsv_upper is None
        ):
            raise InvalidMeasurementError("color_hsv mask needs hsv_lower and hsv_upper")
        if self.min_area_px < 1:
            raise InvalidMeasurementError("min_area_px must be at least 1")
        if not 0 < self.max_area_fraction <= 1:
            raise InvalidMeasurementError("max_area_fraction must be in (0, 1]")
        for name, kernel in (("blur", self.blur_kernel_px), ("open", self.open_kernel_px)):
            if kernel < 0 or (kernel and kernel % 2 == 0):
                raise InvalidMeasurementError(f"{name}_kernel_px must be 0 or an odd number")
        if self.frame_step < 1:
            raise InvalidMeasurementError("frame_step must be at least 1")
        if self.max_jump_px_per_frame is not None and self.max_jump_px_per_frame <= 0:
            raise InvalidMeasurementError("max_jump_px_per_frame must be positive")
        if self.start_s is not None and self.end_s is not None and self.end_s <= self.start_s:
            raise InvalidMeasurementError("end_s must be greater than start_s")


@dataclass(frozen=True, slots=True)
class FrameObservation:
    """What the tracker saw in one analysed frame. Pixel values use full-frame coordinates."""

    frame: int
    time_s: float
    status: FrameStatus
    edge_px: float | None = None  # leading-edge coordinate along the configured axis
    bbox: tuple[int, int, int, int] | None = None  # x, y, width, height of the region
    area_px: int | None = None
    candidates: int = 0  # regions that passed the area limits in this frame
    saturated_fraction: float | None = None  # share of region pixels at saturation level
    background_change: float | None = None  # mean abs gray difference outside the ROI


@dataclass(frozen=True, slots=True)
class PixelTrack:
    """Uncalibrated track. Positions are pixels; nothing here is a physical length."""

    video_uri: str
    feature: TrackedFeature
    frame_width: int
    frame_height: int
    container_fps: float | None  # as reported by the file; None when missing or invalid
    fps_used: float
    fps_source: str  # "container" | "override" | "calibration"
    frames_decoded: int
    observations: tuple[FrameObservation, ...]
    config: TrackerConfig
    opencv_version: str

    @property
    def detections(self) -> tuple[FrameObservation, ...]:
        return tuple(o for o in self.observations if o.status is FrameStatus.DETECTED)


@dataclass(frozen=True, slots=True)
class LinearFit:
    """Least-squares line edge_px = intercept + slope * time_s over detected frames."""

    slope_px_per_s: float  # in image coordinates: negative when moving left or up
    intercept_px: float
    r_squared: float | None  # None when the edge never moves (zero variance)
    rms_residual_px: float
    samples: int


@dataclass(frozen=True, slots=True)
class SuitabilityLimits:
    """Thresholds for the SUITABLE / NOT SUITABLE verdict. Exported with each verdict."""

    min_detections: int = 5
    min_coverage: float = 0.8
    max_spurious_fraction: float = 0.1
    max_median_saturated_fraction: float = 0.5
    max_background_change: float = 8.0  # gray levels, 95th percentile across frames


@dataclass(frozen=True, slots=True)
class TrackDiagnostics:
    frames_analysed: int
    detected: int
    no_detection: int
    spurious_jumps: int
    coverage: float  # detected / analysed
    longest_gap_frames: int  # longest run of analysed frames without a detection
    fit: LinearFit | None
    # Positive when the edge advances in the configured direction. Pixels per second.
    advance_px_per_s: float | None
    # Share of consecutive detections that advance (or hold) in the configured direction.
    # Reported for inspection only: non-monotonic samples are never removed.
    monotonic_fraction: float | None
    median_saturated_fraction: float | None
    background_change_p95: float | None  # None when no ROI was set (not assessed)
    suitable: bool
    reasons: tuple[str, ...]  # why the video is NOT SUITABLE; empty when suitable
    warnings: tuple[str, ...]
    limits: SuitabilityLimits


def fit_edge_vs_time(observations: Sequence[FrameObservation]) -> LinearFit | None:
    """Ordinary least squares over DETECTED frames. Needs at least 3 distinct times."""
    points = [
        (o.time_s, o.edge_px)
        for o in observations
        if o.status is FrameStatus.DETECTED and o.edge_px is not None
    ]
    if len(points) < 3:
        return None
    n = len(points)
    t_mean = sum(t for t, _ in points) / n
    x_mean = sum(x for _, x in points) / n
    denom = sum((t - t_mean) ** 2 for t, _ in points)
    if denom == 0:
        return None
    slope = sum((t - t_mean) * (x - x_mean) for t, x in points) / denom
    intercept = x_mean - slope * t_mean
    ss_res = sum((x - (intercept + slope * t)) ** 2 for t, x in points)
    ss_tot = sum((x - x_mean) ** 2 for _, x in points)
    return LinearFit(
        slope_px_per_s=slope,
        intercept_px=intercept,
        r_squared=None if ss_tot == 0 else 1.0 - ss_res / ss_tot,
        rms_residual_px=math.sqrt(ss_res / n),
        samples=n,
    )


def diagnose(track: PixelTrack, limits: SuitabilityLimits | None = None) -> TrackDiagnostics:
    """Coverage, gaps, fit and the SUITABLE / NOT SUITABLE verdict for a pixel track."""
    limits = limits or SuitabilityLimits()
    obs = track.observations
    detections = track.detections
    analysed = len(obs)
    spurious = sum(1 for o in obs if o.status is FrameStatus.SPURIOUS_JUMP)
    missing = sum(1 for o in obs if o.status is FrameStatus.NO_DETECTION)
    coverage = len(detections) / analysed if analysed else 0.0

    longest_gap = gap = 0
    for o in obs:
        gap = 0 if o.status is FrameStatus.DETECTED else gap + 1
        longest_gap = max(longest_gap, gap)

    sign = 1.0 if track.config.direction is Direction.INCREASING else -1.0
    fit = fit_edge_vs_time(obs)
    advance = sign * fit.slope_px_per_s if fit else None

    edges = [o.edge_px for o in detections if o.edge_px is not None]
    monotonic: float | None = None
    if len(edges) >= 2:
        steps = [sign * (b - a) for a, b in itertools.pairwise(edges)]
        monotonic = sum(1 for s in steps if s >= -1.0) / len(steps)  # 1 px tolerance

    saturated = _median([o.saturated_fraction for o in detections])
    background = _percentile([o.background_change for o in obs], 0.95)

    reasons: list[str] = []
    warnings: list[str] = []
    if analysed == 0:
        reasons.append("no frames were analysed (empty video or empty time window)")
    if len(detections) < limits.min_detections:
        reasons.append(
            f"only {len(detections)} detected frames (minimum {limits.min_detections}): "
            "flame not visible to this mask"
        )
    if analysed and coverage < limits.min_coverage:
        reasons.append(
            f"tracking coverage {coverage:.0%} is below {limits.min_coverage:.0%}: "
            "flame invisible, occluded or outside the ROI for much of the window"
        )
    if analysed and spurious / analysed > limits.max_spurious_fraction:
        reasons.append(
            f"{spurious} spurious jumps in {analysed} frames: "
            "the tracked region is not stable (reflections, noise or several flames)"
        )
    if saturated is not None and saturated > limits.max_median_saturated_fraction:
        reasons.append(
            f"median {saturated:.0%} of the tracked region is saturated: "
            "the luminous edge is set by sensor clipping, not by the flame"
        )
    if background is not None and background > limits.max_background_change:
        reasons.append(
            f"scene outside the ROI changes by {background:.1f} gray levels (95th percentile): "
            "camera motion or lighting change"
        )
    if track.config.roi is None:
        warnings.append("no ROI set: camera stability was not assessed")
    if advance is not None and advance < 0:
        warnings.append(
            "net edge motion is opposite to the configured direction: "
            "check the direction setting or that the right edge is tracked"
        )
    if monotonic is not None and monotonic < 0.9:
        warnings.append(
            f"only {monotonic:.0%} of steps advance in the configured direction "
            "(samples were kept; a single straight-line fit may not describe this track)"
        )
    if fit is None and len(detections) >= limits.min_detections:
        warnings.append("no linear fit: all detections share one timestamp")

    return TrackDiagnostics(
        frames_analysed=analysed,
        detected=len(detections),
        no_detection=missing,
        spurious_jumps=spurious,
        coverage=coverage,
        longest_gap_frames=longest_gap,
        fit=fit,
        advance_px_per_s=advance,
        monotonic_fraction=monotonic,
        median_saturated_fraction=saturated,
        background_change_p95=background,
        suitable=not reasons,
        reasons=tuple(reasons),
        warnings=tuple(warnings),
        limits=limits,
    )


def _median(values: Sequence[float | None]) -> float | None:
    return _percentile(values, 0.5)


def _percentile(values: Sequence[float | None], q: float) -> float | None:
    """Nearest-rank percentile over the non-None values."""
    present = sorted(v for v in values if v is not None)
    if not present:
        return None
    return present[min(len(present) - 1, max(0, math.ceil(q * len(present)) - 1))]


def _load_cv2() -> Any:
    # Lazy and untyped on purpose: OpenCV is an optional extra, and the API process and CI
    # must import this module without it.
    try:
        return importlib.import_module("cv2")
    except ImportError as exc:  # pragma: no cover - depends on the environment
        raise RuntimeError(
            "OpenCV is not installed. Run `uv sync --extra vision` to use FlameVision."
        ) from exc


class OpenCvFlameDetector:
    """Tracks the luminous leading edge of the brightest plausible region in a video."""

    def __init__(
        self,
        threshold: int = 200,
        min_area_px: int = 25,
        frame_step: int = 1,
        *,
        config: TrackerConfig | None = None,
        limits: SuitabilityLimits | None = None,
    ) -> None:
        self._config = config or TrackerConfig(
            threshold=threshold, min_area_px=min_area_px, frame_step=max(1, frame_step)
        )
        self._limits = limits or SuitabilityLimits()

    @property
    def config(self) -> TrackerConfig:
        return self._config

    # -- port -----------------------------------------------------------------------------

    def track(self, trial_id: str, video_uri: str, calibration: Calibration) -> FlameFrontTrack:
        return self.track_with_diagnostics(trial_id, video_uri, calibration)[0]

    def track_with_diagnostics(
        self, trial_id: str, video_uri: str, calibration: Calibration
    ) -> tuple[FlameFrontTrack, PixelTrack, TrackDiagnostics]:
        """Calibrated track plus the pixel-level evidence it was built from.

        Position is measured along the configured direction of advance, so a flame moving
        the expected way has increasing ``position_mm`` whether it travels left or right.
        """
        pixel_track = self._run(video_uri, calibration.fps, "calibration")
        diagnostics = diagnose(pixel_track, self._limits)
        sign = 1.0 if self._config.direction is Direction.INCREASING else -1.0
        samples = tuple(
            FrontSample(
                frame=o.frame,
                time_s=o.time_s,
                position_mm=sign * (o.edge_px - calibration.origin_px) * calibration.mm_per_pixel,
            )
            for o in pixel_track.detections
            if o.edge_px is not None
        )
        notes = [
            f"luminous leading edge along {self._config.axis.value} "
            f"({self._config.direction.value}), mask={self._config.mask_mode.value}, "
            f"coverage {diagnostics.coverage:.0%}, OpenCV {pixel_track.opencv_version}"
        ]
        container = pixel_track.container_fps
        if container is not None and abs(container - calibration.fps) > 0.01 * calibration.fps:
            notes.append(
                f"calibration fps {calibration.fps:g} differs from the container fps "
                f"{container:g}: times follow the calibration"
            )
        notes.extend(diagnostics.warnings)
        if diagnostics.suitable:
            status = ValidationStatus.UNVALIDATED
        else:
            status = ValidationStatus.REJECTED
            notes.insert(0, "NOT SUITABLE: " + "; ".join(diagnostics.reasons))
        track = FlameFrontTrack(
            trial_id=trial_id,
            video_uri=video_uri,
            feature=TrackedFeature.LUMINOUS_LEADING_EDGE,
            calibration=calibration,
            samples=samples,
            validation=status,
            validation_note=". ".join(notes),
        )
        return track, pixel_track, diagnostics

    # -- uncalibrated analysis --------------------------------------------------------------

    def track_pixels(self, video_uri: str, fps_override: float | None = None) -> PixelTrack:
        """Track in pixels. Times use the container FPS unless ``fps_override`` is given."""
        if fps_override is not None:
            return self._run(video_uri, _valid_fps(fps_override, "fps_override"), "override")
        return self._run(video_uri, None, "container")

    def _run(self, video_uri: str, fps: float | None, fps_source: str) -> PixelTrack:
        cv2 = _load_cv2()
        cfg = self._config
        cap = cv2.VideoCapture(video_uri)
        if not cap.isOpened():
            cap.release()
            raise FileNotFoundError(f"Cannot open video '{video_uri}'")
        try:
            raw_fps = float(cap.get(cv2.CAP_PROP_FPS))
            container_fps = raw_fps if _is_valid_fps(raw_fps) else None
            if fps is None:
                if container_fps is None:
                    raise InvalidMeasurementError(
                        f"Video '{video_uri}' reports an invalid frame rate ({raw_fps!r}). "
                        "Provide the real FPS explicitly; times cannot be derived otherwise."
                    )
                fps = container_fps
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            roi = _clip_roi(cfg.roi, width, height)

            observations: list[FrameObservation] = []
            anchor: tuple[int, float, float, float] | None = None  # frame, edge, cx, cy
            previous_gray: Any = None
            frame_idx = 0
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                time_s = frame_idx / fps
                in_window = (cfg.start_s is None or time_s >= cfg.start_s) and (
                    cfg.end_s is None or time_s <= cfg.end_s
                )
                if in_window and frame_idx % cfg.frame_step == 0:
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    background = (
                        _background_change(cv2, gray, previous_gray, roi)
                        if cfg.roi is not None
                        else None
                    )
                    previous_gray = gray
                    observation, anchor = self._observe(
                        cv2, frame, gray, roi, frame_idx, time_s, anchor, background
                    )
                    observations.append(observation)
                frame_idx += 1
        finally:
            cap.release()
        return PixelTrack(
            video_uri=video_uri,
            feature=TrackedFeature.LUMINOUS_LEADING_EDGE,
            frame_width=width,
            frame_height=height,
            container_fps=container_fps,
            fps_used=fps,
            fps_source=fps_source,
            frames_decoded=frame_idx,
            observations=tuple(observations),
            config=cfg,
            opencv_version=str(cv2.__version__),
        )

    def _observe(
        self,
        cv2: Any,
        frame: Any,
        gray: Any,
        roi: tuple[int, int, int, int],
        frame_idx: int,
        time_s: float,
        anchor: tuple[int, float, float, float] | None,
        background: float | None,
    ) -> tuple[FrameObservation, tuple[int, float, float, float] | None]:
        cfg = self._config
        rx, ry, rw, rh = roi
        gray_roi = gray[ry : ry + rh, rx : rx + rw]
        work = gray_roi
        color_roi = frame[ry : ry + rh, rx : rx + rw]
        if cfg.blur_kernel_px:
            kernel = (cfg.blur_kernel_px, cfg.blur_kernel_px)
            work = cv2.GaussianBlur(work, kernel, 0)
            color_roi = cv2.GaussianBlur(color_roi, kernel, 0)
        if cfg.mask_mode is MaskMode.COLOR_HSV:
            hsv = cv2.cvtColor(color_roi, cv2.COLOR_BGR2HSV)
            mask = cv2.inRange(hsv, cfg.hsv_lower, cfg.hsv_upper)
        else:
            # `>= threshold`, so threshold=255 still matches fully saturated pixels.
            mask = cv2.inRange(work, cfg.threshold, 255)
        if cfg.open_kernel_px:
            element = cv2.getStructuringElement(
                cv2.MORPH_ELLIPSE, (cfg.open_kernel_px, cfg.open_kernel_px)
            )
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, element)

        count, labels, stats, centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)
        max_area = cfg.max_area_fraction * rw * rh
        candidates = [
            label
            for label in range(1, count)
            if cfg.min_area_px <= int(stats[label, cv2.CC_STAT_AREA]) <= max_area
        ]
        if not candidates:
            missing = FrameObservation(
                frame_idx, time_s, FrameStatus.NO_DETECTION, background_change=background
            )
            return missing, anchor

        if anchor is None:
            # Nothing to be continuous with yet: start from the largest plausible region.
            chosen = max(candidates, key=lambda label: int(stats[label, cv2.CC_STAT_AREA]))
        else:
            # Afterwards prefer continuity over size, so a bigger reflection that appears
            # later does not steal the track.
            _, _, ax, ay = anchor
            chosen = min(
                candidates,
                key=lambda label: (
                    (float(centroids[label][0]) + rx - ax) ** 2
                    + (float(centroids[label][1]) + ry - ay) ** 2
                ),
            )
        x = int(stats[chosen, cv2.CC_STAT_LEFT]) + rx
        y = int(stats[chosen, cv2.CC_STAT_TOP]) + ry
        w = int(stats[chosen, cv2.CC_STAT_WIDTH])
        h = int(stats[chosen, cv2.CC_STAT_HEIGHT])
        area = int(stats[chosen, cv2.CC_STAT_AREA])
        low, extent = (x, w) if cfg.axis is Axis.X else (y, h)
        edge = float(low + extent - 1 if cfg.direction is Direction.INCREASING else low)
        region = labels == chosen
        saturated = float((gray_roi[region] >= cfg.saturation_level).sum()) / area

        status = FrameStatus.DETECTED
        if anchor is not None and cfg.max_jump_px_per_frame is not None:
            anchor_frame, anchor_edge, _, _ = anchor
            allowed = cfg.max_jump_px_per_frame * (frame_idx - anchor_frame)
            if abs(edge - anchor_edge) > allowed:
                status = FrameStatus.SPURIOUS_JUMP
        observation = FrameObservation(
            frame=frame_idx,
            time_s=time_s,
            status=status,
            edge_px=edge,
            bbox=(x, y, w, h),
            area_px=area,
            candidates=len(candidates),
            saturated_fraction=saturated,
            background_change=background,
        )
        if status is FrameStatus.DETECTED:
            anchor = (
                frame_idx,
                edge,
                float(centroids[chosen][0]) + rx,
                float(centroids[chosen][1]) + ry,
            )
        return observation, anchor


def _is_valid_fps(fps: float) -> bool:
    return math.isfinite(fps) and 0 < fps <= _MAX_PLAUSIBLE_FPS


def _valid_fps(fps: float, name: str) -> float:
    if not _is_valid_fps(fps):
        raise InvalidMeasurementError(f"{name} must be a positive, finite frame rate")
    return fps


def _clip_roi(roi: Roi | None, width: int, height: int) -> tuple[int, int, int, int]:
    if roi is None:
        return 0, 0, width, height
    if roi.x >= width or roi.y >= height:
        raise InvalidMeasurementError(
            f"ROI origin ({roi.x}, {roi.y}) is outside the {width}x{height} frame"
        )
    return roi.x, roi.y, min(roi.width, width - roi.x), min(roi.height, height - roi.y)


def _background_change(
    cv2: Any, gray: Any, previous_gray: Any, roi: tuple[int, int, int, int]
) -> float | None:
    """Mean absolute gray difference to the previous analysed frame, outside the ROI."""
    if previous_gray is None:
        return None
    rx, ry, rw, rh = roi
    diff = cv2.absdiff(gray, previous_gray)
    outside_pixels = diff.size - rw * rh
    if outside_pixels <= 0:
        return None
    outside_sum = float(diff.sum()) - float(diff[ry : ry + rh, rx : rx + rw].sum())
    return outside_sum / float(outside_pixels)
