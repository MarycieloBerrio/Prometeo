"""FlameFrontDetector using OpenCV luminosity thresholding (requires the `vision` extra).

Tracks the LUMINOUS LEADING EDGE along the x axis of the frame. This is not the reaction
front; results stay UNVALIDATED until compared against a reference measurement.
"""

from __future__ import annotations

from prometeo.domain.flamevision.model import (
    Calibration,
    FlameFrontTrack,
    FrontSample,
    TrackedFeature,
)


class OpenCvFlameDetector:
    def __init__(self, threshold: int = 200, min_area_px: int = 25, frame_step: int = 1) -> None:
        self._threshold = threshold
        self._min_area = min_area_px
        self._step = max(1, frame_step)

    def track(self, trial_id: str, video_uri: str, calibration: Calibration) -> FlameFrontTrack:
        import cv2  # lazy: keeps OpenCV optional for the API process

        cap = cv2.VideoCapture(video_uri)
        if not cap.isOpened():
            raise FileNotFoundError(f"Cannot open video '{video_uri}'")
        samples: list[FrontSample] = []
        frame_idx = 0
        try:
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                if frame_idx % self._step == 0:
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    _, mask = cv2.threshold(gray, self._threshold, 255, cv2.THRESH_BINARY)
                    contours, _ = cv2.findContours(
                        mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
                    )
                    contours = [c for c in contours if cv2.contourArea(c) >= self._min_area]
                    if contours:
                        largest = max(contours, key=cv2.contourArea)
                        x, _, w, _ = cv2.boundingRect(largest)
                        edge_px = float(x + w)
                        samples.append(
                            FrontSample(
                                frame=frame_idx,
                                time_s=frame_idx / calibration.fps,
                                position_mm=(edge_px - calibration.origin_px)
                                * calibration.mm_per_pixel,
                            )
                        )
                frame_idx += 1
        finally:
            cap.release()
        return FlameFrontTrack(
            trial_id=trial_id,
            video_uri=video_uri,
            feature=TrackedFeature.LUMINOUS_LEADING_EDGE,
            calibration=calibration,
            samples=tuple(samples),
        )
