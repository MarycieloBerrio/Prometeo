"""FlameVision offline tracker: video in, auditable track out.

Run from `apps/backend` so the `prometeo` package and the `vision` extra are available:

    uv run --extra vision python ../../tools/flamevision/track_video.py VIDEO --out-dir OUT ...

Outputs (all derived; the input video is opened read-only and never modified):

    track.csv      one row per analysed frame, including frames with no detection
    track.json     the same observations plus source, method, parameters, diagnostics, verdict
    curve.png      edge position against time, with the fitted line
    keyframes.jpg  contact sheet of overlay frames (with --keyframes N)
    overlay.mp4    overlay video (with --overlay)
    manifest.json  index of the files above for the UI

Units are honest by construction. Without `--mm-per-pixel` every position is in pixels and
every rate in pixels/second; millimetres appear only with a calibration AND its source.
The tracked feature is the luminous leading edge, not the reaction front.
"""

from __future__ import annotations

import argparse
import csv
import dataclasses
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from prometeo.adapters.outbound.vision.opencv_flame_detector import (
    Axis,
    Direction,
    FrameStatus,
    MaskMode,
    OpenCvFlameDetector,
    PixelTrack,
    Roi,
    SuitabilityLimits,
    TrackDiagnostics,
    TrackerConfig,
    diagnose,
)
from prometeo.domain.physics.metrics import flame_spread_velocity_fit
from prometeo.domain.shared.errors import DomainError
from prometeo.domain.shared.quantity import Quantity

SCHEMA = "prometeo.flamevision.track/v1"
FEATURE_NOTE = (
    "Luminous leading edge of the thresholded flame image. It is not the reaction front, "
    "the pyrolysis front, a temperature or a heat-release rate."
)
CSV_COLUMNS_PX = [
    "frame",
    "time_s",
    "status",
    "edge_px",
    "bbox_x_px",
    "bbox_y_px",
    "bbox_w_px",
    "bbox_h_px",
    "area_px",
    "candidates",
    "saturated_fraction",
    "background_change",
]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    p.add_argument("video", type=Path)
    p.add_argument("--out-dir", type=Path, required=True)
    g = p.add_argument_group("tracking")
    g.add_argument("--roi", help="x,y,width,height in pixels (top-left origin)")
    g.add_argument("--axis", choices=[a.value for a in Axis], default=Axis.X.value)
    g.add_argument(
        "--direction",
        choices=[d.value for d in Direction],
        default=Direction.INCREASING.value,
        help="increasing = flame advances right (x) or down (y)",
    )
    g.add_argument("--mask", choices=[m.value for m in MaskMode], default="luminance")
    g.add_argument("--threshold", type=int, default=200, help="gray level 0..255")
    g.add_argument("--hsv-lower", help="h,s,v (OpenCV ranges: H 0..179, S and V 0..255)")
    g.add_argument("--hsv-upper", help="h,s,v")
    g.add_argument("--min-area", type=int, default=25, help="pixels")
    g.add_argument("--max-area-fraction", type=float, default=0.5, help="of the ROI area")
    g.add_argument("--blur", type=int, default=0, help="Gaussian kernel, odd; 0 = off")
    g.add_argument("--open", type=int, default=3, help="opening kernel, odd; 0 = off")
    g.add_argument("--frame-step", type=int, default=1)
    g.add_argument("--start-s", type=float)
    g.add_argument("--end-s", type=float)
    g.add_argument("--max-jump", type=float, help="pixels per frame; larger = spurious")
    g.add_argument("--fps", type=float, help="override the container FPS (state why in notes)")
    s = p.add_argument_group("suitability limits")
    s.add_argument("--min-coverage", type=float, default=SuitabilityLimits().min_coverage)
    s.add_argument("--min-detections", type=int, default=SuitabilityLimits().min_detections)
    c = p.add_argument_group("calibration and validation (optional; never guessed)")
    c.add_argument("--mm-per-pixel", type=float)
    c.add_argument("--origin-px", type=float, default=0.0)
    c.add_argument("--calibration-source", help="where the scale comes from (required)")
    c.add_argument("--reference-mm-s", type=float, help="published spread rate to compare")
    c.add_argument("--reference-source", help="citation for the reference (required)")
    c.add_argument("--tolerance-pct", type=float, default=10.0)
    m = p.add_argument_group("provenance (recorded as given, never invented)")
    m.add_argument("--source-url")
    m.add_argument("--source-license")
    m.add_argument("--trial-key", help="the source's own test label, e.g. 'PSI-25 test B9'")
    m.add_argument("--trial-id", help="Prometeo Trial.id, only if the link was verified")
    m.add_argument("--notes")
    o = p.add_argument_group("extra outputs")
    o.add_argument("--overlay", action="store_true", help="write overlay.mp4")
    o.add_argument("--keyframes", type=int, default=0, help="write keyframes.jpg with N frames")
    return p


def _ints(text: str, count: int, name: str) -> tuple[int, ...]:
    parts = text.split(",")
    if len(parts) != count:
        raise SystemExit(f"error: {name} needs {count} comma-separated integers")
    return tuple(int(x) for x in parts)


def config_from_args(args: argparse.Namespace) -> TrackerConfig:
    roi = None
    if args.roi:
        x, y, w, h = _ints(args.roi, 4, "--roi")
        roi = Roi(x, y, w, h)
    lower = _ints(args.hsv_lower, 3, "--hsv-lower") if args.hsv_lower else None
    upper = _ints(args.hsv_upper, 3, "--hsv-upper") if args.hsv_upper else None
    return TrackerConfig(
        threshold=args.threshold,
        mask_mode=MaskMode(args.mask),
        hsv_lower=lower,
        hsv_upper=upper,
        roi=roi,
        axis=Axis(args.axis),
        direction=Direction(args.direction),
        min_area_px=args.min_area,
        max_area_fraction=args.max_area_fraction,
        blur_kernel_px=args.blur,
        open_kernel_px=args.open,
        frame_step=args.frame_step,
        start_s=args.start_s,
        end_s=args.end_s,
        max_jump_px_per_frame=args.max_jump,
    )


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def physical_result(
    track: PixelTrack, diagnostics: TrackDiagnostics, args: argparse.Namespace
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Millimetre results and validation status. Returns (physical, validation)."""
    if args.mm_per_pixel is None:
        return None, {
            "status": "UNVALIDATED",
            "reason": "No verifiable mm/pixel scale: results are pixel-only and cannot be "
            "compared with a published spread rate.",
            "reference": None,
        }
    sign = 1.0 if track.config.direction is Direction.INCREASING else -1.0
    positions = [
        Quantity(sign * (o.edge_px - args.origin_px) * args.mm_per_pixel, "mm")
        for o in track.detections
        if o.edge_px is not None
    ]
    times = [Quantity(o.time_s, "s") for o in track.detections]
    calibration = {
        "mm_per_pixel": args.mm_per_pixel,
        "origin_px": args.origin_px,
        "source": args.calibration_source,
    }
    if not diagnostics.suitable or diagnostics.fit is None:
        return (
            {"calibration": calibration, "spread_velocity": None},
            {
                "status": "UNVALIDATED",
                "reason": "Video is NOT SUITABLE; no velocity was derived.",
                "reference": None,
            },
        )
    velocity = flame_spread_velocity_fit(positions, times)  # deterministic domain metric
    physical = {
        "calibration": calibration,
        "spread_velocity": {
            "value": velocity.value,
            "unit": velocity.unit,
            "quality": "derived",
            "method": "least-squares slope of luminous leading edge position vs time "
            "(prometeo.domain.physics.metrics.flame_spread_velocity_fit)",
        },
    }
    if args.reference_mm_s is None:
        return physical, {
            "status": "UNVALIDATED",
            "reason": "No reference value was provided for comparison.",
            "reference": None,
        }
    absolute = velocity.value - args.reference_mm_s
    relative_pct = 100.0 * absolute / args.reference_mm_s
    within = abs(relative_pct) <= args.tolerance_pct
    return physical, {
        "status": "VALIDATED" if within else "REJECTED",
        "reason": f"|relative error| {'<=' if within else '>'} {args.tolerance_pct:g} % tolerance",
        "reference": {
            "value": args.reference_mm_s,
            "unit": "mm/s",
            "source": args.reference_source,
        },
        "absolute_error": {"value": absolute, "unit": "mm/s"},
        "relative_error_pct": relative_pct,
        "tolerance_pct": args.tolerance_pct,
    }


def write_csv(path: Path, track: PixelTrack, args: argparse.Namespace) -> list[str]:
    columns = list(CSV_COLUMNS_PX)
    calibrated = args.mm_per_pixel is not None
    if calibrated:
        columns.insert(4, "position_mm")
    sign = 1.0 if track.config.direction is Direction.INCREASING else -1.0
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(columns)
        for o in track.observations:
            bbox = o.bbox or ("", "", "", "")
            row: list[Any] = [
                o.frame,
                f"{o.time_s:.6f}",
                o.status.value,
                "" if o.edge_px is None else f"{o.edge_px:.1f}",
                *bbox,
                "" if o.area_px is None else o.area_px,
                o.candidates,
                "" if o.saturated_fraction is None else f"{o.saturated_fraction:.4f}",
                "" if o.background_change is None else f"{o.background_change:.3f}",
            ]
            if calibrated:
                mm = (
                    ""
                    if o.edge_px is None
                    else f"{sign * (o.edge_px - args.origin_px) * args.mm_per_pixel:.4f}"
                )
                row.insert(4, mm)
            writer.writerow(row)
    return columns


def _draw_overlay(cv2: Any, frame: Any, track: PixelTrack, obs: Any, verdict: str) -> Any:
    cfg = track.config
    height, width = frame.shape[:2]
    if cfg.roi is not None:
        r = cfg.roi
        cv2.rectangle(frame, (r.x, r.y), (r.x + r.width - 1, r.y + r.height - 1), (255, 200, 0), 1)
    if obs is not None and obs.bbox is not None:
        ok = obs.status is FrameStatus.DETECTED
        color = (0, 255, 0) if ok else (0, 0, 255)
        x, y, w, h = obs.bbox
        cv2.rectangle(frame, (x, y), (x + w - 1, y + h - 1), color, 1)
        e = round(obs.edge_px)
        if cfg.axis is Axis.X:
            cv2.line(frame, (e, 0), (e, height - 1), color, 1)
        else:
            cv2.line(frame, (0, e), (width - 1, e), color, 1)
    status = obs.status.value if obs is not None else "not analysed"
    edge = f"{obs.edge_px:.0f} px" if obs is not None and obs.edge_px is not None else "-"
    time_s = f"t={obs.time_s:.2f} s" if obs is not None else ""
    lines = [
        f"{time_s}  edge {cfg.axis.value}={edge}  [{status}]",
        f"luminous leading edge (not reaction front) | {verdict}",
    ]
    for i, text in enumerate(lines):
        org = (6, height - 10 - 16 * (len(lines) - 1 - i))
        cv2.putText(frame, text, org, cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 0, 0), 3, cv2.LINE_AA)
        cv2.putText(
            frame, text, org, cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 255), 1, cv2.LINE_AA
        )
    return frame


def write_visuals(
    video: Path, out_dir: Path, track: PixelTrack, verdict: str, overlay: bool, keyframes: int
) -> list[str]:
    """Second read-only pass over the video to render overlay.mp4 and/or keyframes.jpg."""
    import cv2  # the detector already required it
    import numpy as np

    by_frame = {o.frame: o for o in track.observations}
    if not by_frame or not (overlay or keyframes):
        return []
    first, last = min(by_frame), max(by_frame)
    detected = [o.frame for o in track.detections] or sorted(by_frame)
    span = max(1, keyframes - 1)
    picks = {detected[round(i * (len(detected) - 1) / span)] for i in range(keyframes)}
    written: list[str] = []
    writer = None
    if overlay:
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        size = (track.frame_width, track.frame_height)
        writer = cv2.VideoWriter(str(out_dir / "overlay.mp4"), fourcc, track.fps_used, size)
        written.append("overlay.mp4")
    tiles = []
    cap = cv2.VideoCapture(str(video))
    index = 0
    last_obs = None
    try:
        while True:
            ok, frame = cap.read()
            if not ok or index > last:
                break
            if index >= first:
                last_obs = by_frame.get(index, last_obs if track.config.frame_step > 1 else None)
                frame = _draw_overlay(cv2, frame, track, by_frame.get(index, last_obs), verdict)
                if writer is not None:
                    writer.write(frame)
                if index in picks:
                    scale = 480 / frame.shape[1]
                    tiles.append(cv2.resize(frame, None, fx=scale, fy=scale))
            index += 1
    finally:
        cap.release()
        if writer is not None:
            writer.release()
    if tiles:
        per_row = 2
        while len(tiles) % per_row:
            tiles.append(np.zeros_like(tiles[0]))
        rows = [np.hstack(tiles[i : i + per_row]) for i in range(0, len(tiles), per_row)]
        cv2.imwrite(str(out_dir / "keyframes.jpg"), np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 82])
        written.append("keyframes.jpg")
    return written


def write_curve(path: Path, track: PixelTrack, diagnostics: TrackDiagnostics) -> bool:
    """Position-vs-time plot drawn with OpenCV (no plotting dependency)."""
    import cv2
    import numpy as np

    points = [o for o in track.observations if o.edge_px is not None]
    if len(points) < 2:
        return False
    width, height, left, right, top, bottom = 720, 420, 70, 20, 40, 50
    canvas = np.full((height, width, 3), 255, np.uint8)
    t0, t1 = points[0].time_s, points[-1].time_s
    edges = [o.edge_px for o in points if o.edge_px is not None]
    e0, e1 = min(edges), max(edges)
    t_span, e_span = max(t1 - t0, 1e-9), max(e1 - e0, 1.0)

    def to_xy(t: float, e: float) -> tuple[int, int]:
        px = left + (t - t0) / t_span * (width - left - right)
        py = height - bottom - (e - e0) / e_span * (height - top - bottom)
        return round(px), round(py)

    black, gray = (0, 0, 0), (150, 150, 150)
    cv2.rectangle(canvas, (left, top), (width - right, height - bottom), gray, 1)
    font = cv2.FONT_HERSHEY_SIMPLEX
    for i in range(5):
        t = t0 + t_span * i / 4
        e = e0 + e_span * i / 4
        x, _ = to_xy(t, e0)
        _, y = to_xy(t0, e)
        cv2.putText(canvas, f"{t:.1f}", (x - 14, height - bottom + 16), font, 0.4, black, 1)
        cv2.putText(canvas, f"{e:.0f}", (8, y + 4), font, 0.4, black, 1)
    axis = track.config.axis.value
    cv2.putText(canvas, "time [s]", (width // 2 - 30, height - 12), font, 0.45, black, 1)
    title = f"luminous leading edge {axis} [px] vs time (uncalibrated pixels)"
    cv2.putText(canvas, title, (left, 24), font, 0.45, black, 1)
    for o in points:
        if o.edge_px is None:
            continue
        ok = o.status is FrameStatus.DETECTED
        cv2.circle(canvas, to_xy(o.time_s, o.edge_px), 2, (200, 90, 0) if ok else (0, 0, 220), -1)
    fit = diagnostics.fit
    if fit is not None:
        a = to_xy(t0, fit.intercept_px + fit.slope_px_per_s * t0)
        b = to_xy(t1, fit.intercept_px + fit.slope_px_per_s * t1)
        cv2.line(canvas, a, b, (0, 140, 0), 1, cv2.LINE_AA)
        label = f"fit slope {fit.slope_px_per_s:.2f} px/s (image coords), n={fit.samples}"
        cv2.putText(canvas, label, (left + 8, top + 18), font, 0.42, (0, 110, 0), 1)
    cv2.imwrite(str(path), canvas)
    return True


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if (args.mm_per_pixel is None) != (args.calibration_source is None):
        raise SystemExit("error: --mm-per-pixel and --calibration-source must be given together")
    if args.mm_per_pixel is not None and args.mm_per_pixel <= 0:
        raise SystemExit("error: --mm-per-pixel must be positive")
    if (args.reference_mm_s is None) != (args.reference_source is None):
        raise SystemExit("error: --reference-mm-s and --reference-source must be given together")
    if args.reference_mm_s is not None and args.mm_per_pixel is None:
        raise SystemExit("error: a reference in mm/s needs a calibrated track (--mm-per-pixel)")
    if args.reference_mm_s is not None and args.reference_mm_s == 0:
        raise SystemExit("error: --reference-mm-s must be non-zero")
    if not args.video.is_file():
        raise SystemExit(f"error: video not found: {args.video}")

    try:
        config = config_from_args(args)
        limits = SuitabilityLimits(
            min_coverage=args.min_coverage, min_detections=args.min_detections
        )
        detector = OpenCvFlameDetector(config=config, limits=limits)
        track = detector.track_pixels(str(args.video), fps_override=args.fps)
        diagnostics = diagnose(track, limits)
        physical, validation = physical_result(track, diagnostics, args)
    except (DomainError, FileNotFoundError) as exc:
        raise SystemExit(f"error: {exc}") from exc

    verdict = "SUITABLE" if diagnostics.suitable else "NOT_SUITABLE"
    out_dir: Path = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    columns = write_csv(out_dir / "track.csv", track, args)
    files = ["track.csv", "track.json"]
    if write_curve(out_dir / "curve.png", track, diagnostics):
        files.append("curve.png")
    label = f"{verdict} | {validation['status']}"
    files += write_visuals(args.video, out_dir, track, label, args.overlay, args.keyframes)

    units: dict[str, str] = {
        "time_s": "s",
        "edge_px": "px",
        "bbox": "px",
        "area_px": "px^2",
        "rate": "px/s",
        "background_change": "gray levels (0..255)",
    }
    if physical is not None:
        units["position_mm"] = "mm"
    document = {
        "schema": SCHEMA,
        "feature": track.feature.value,
        "feature_note": FEATURE_NOTE,
        "source": {
            "video_file": args.video.name,
            "sha256": sha256_of(args.video),
            "url": args.source_url,
            "license": args.source_license,
            "trial_key": args.trial_key,
            "prometeo_trial_id": args.trial_id,
            "notes": args.notes,
        },
        "video": {
            "width_px": track.frame_width,
            "height_px": track.frame_height,
            "container_fps": track.container_fps,
            "fps_used": track.fps_used,
            "fps_source": track.fps_source,
            "frames_decoded": track.frames_decoded,
        },
        "method": {
            "name": "OpenCvFlameDetector.track_pixels",
            "opencv_version": track.opencv_version,
            "config": dataclasses.asdict(track.config),
        },
        "coordinates": "pixels of the original frame, origin top-left, x right, y down",
        "units": units,
        "diagnostics": dataclasses.asdict(diagnostics),
        "verdict": verdict,
        "validation": validation,
        "physical": physical,
        "observations": [dataclasses.asdict(o) for o in track.observations],
    }
    (out_dir / "track.json").write_text(json.dumps(document, indent=1) + "\n", encoding="utf-8")
    manifest = {
        "schema": "prometeo.flamevision.manifest/v1",
        "trial_key": args.trial_key,
        "prometeo_trial_id": args.trial_id,
        "source_url": args.source_url,
        "source_license": args.source_license,
        "source_sha256": document["source"]["sha256"],
        "feature": track.feature.value,
        "verdict": verdict,
        "validation_status": validation["status"],
        "position_unit": "mm" if physical is not None else "px",
        "rate_unit": "mm/s" if physical is not None else "px/s",
        "csv_columns": columns,
        "files": [*files, "manifest.json"],
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")

    print(
        f"{verdict} | {validation['status']} | coverage {diagnostics.coverage:.1%} "
        f"({diagnostics.detected}/{diagnostics.frames_analysed} frames)"
    )
    if diagnostics.advance_px_per_s is not None:
        print(
            f"advance along {config.axis.value} ({config.direction.value}): "
            f"{diagnostics.advance_px_per_s:.3f} px/s"
        )
    for reason in diagnostics.reasons:
        print(f"  NOT SUITABLE: {reason}")
    for warning in diagnostics.warnings:
        print(f"  warning: {warning}")
    print(f"wrote {', '.join(files)} to {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
