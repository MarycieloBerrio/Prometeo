"""FlameVision domain model.

The luminous region detected in video is NOT necessarily the reaction front, the peak
temperature or the heat-release zone. Every track states which feature it measures.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from prometeo.domain.shared.errors import InvalidMeasurementError


class TrackedFeature(StrEnum):
    LUMINOUS_LEADING_EDGE = "luminous_leading_edge"


class ValidationStatus(StrEnum):
    UNVALIDATED = "unvalidated"
    VALIDATED = "validated"  # checked against a published/reference value
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class Calibration:
    mm_per_pixel: float
    fps: float
    origin_px: float = 0.0

    def __post_init__(self) -> None:
        if self.mm_per_pixel <= 0 or self.fps <= 0:
            raise InvalidMeasurementError("Calibration scale and fps must be positive")


@dataclass(frozen=True, slots=True)
class FrontSample:
    frame: int
    time_s: float
    position_mm: float


@dataclass(frozen=True, slots=True)
class FlameFrontTrack:
    trial_id: str
    video_uri: str
    feature: TrackedFeature
    calibration: Calibration
    samples: tuple[FrontSample, ...]
    validation: ValidationStatus = ValidationStatus.UNVALIDATED
    validation_note: str | None = None
