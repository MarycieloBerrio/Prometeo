"""BASS-II forced-flow speed from the anemometer reading ("Air display").

The PSI-25 experimental table records instrument settings, not flow speed in cm/s. NASA's own
calibration file (PSI-25, Reference Data, `Fan calibration data.xlsx`) gives the conversion:

    U [cm/s] = 1.0066 x Air display

"Based on SPICE fan calibration data at 56 mm downstream, 36 mm from bottom (centerline)".
The file labels this column "example of how to estimate flow": the result is an ESTIMATE of
the centerline speed, always `derived`, never `measured`.

Limits kept here on purpose:
  - Only readings inside the range the calibration tables cover are converted. Lower readings
    are below what the tables resolve, and the file warns that the fan stops at a finite
    voltage, so a reading of 0 is not a calibrated zero flow.
  - The display resolves about 1 cm/s, so the relative error grows at low flow. Speeds
    published by the investigators (from the finer potentiometer calibration) take precedence.
  - Free-text cells ("10 blowoff", "5 down to ext", "0.5 pot") are not interpreted.

TODO(science): confirm the valid range and an uncertainty for the estimate with the BASS-II team.
No uncertainty is stated in the calibration file, so none is reported.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from prometeo.domain.shared.errors import InvalidMeasurementError
from prometeo.domain.shared.quantity import Quantity

BASS2_AIR_DISPLAY_FACTOR = 1.0066
# Smallest non-zero and largest "Air Display" values present in the calibration tables.
BASS2_AIR_DISPLAY_MIN = 2.0
BASS2_AIR_DISPLAY_MAX = 59.0

BASS2_FLOW_METHOD = (
    "U [cm/s] = 1.0066 x Air display. NASA PSI-25 Reference Data, 'Fan calibration data.xlsx' "
    "(based on SPICE fan calibration at 56 mm downstream, 36 mm from bottom, centerline). "
    "Estimate; display resolution about 1 cm/s."
)

_NUMBER = re.compile(r"\d+(?:\.\d+)?")


class FlowDerivationKind(StrEnum):
    SINGLE = "single"  # one reading for the whole test
    STEPPED = "stepped"  # several readings: the flow was changed during the test
    NOT_DERIVABLE = "not_derivable"


@dataclass(frozen=True, slots=True)
class FlowStep:
    air_display: float
    speed: Quantity | None  # None when the reading is outside the calibrated range
    note: str | None = None


@dataclass(frozen=True, slots=True)
class FlowDerivation:
    kind: FlowDerivationKind
    steps: tuple[FlowStep, ...] = ()
    reason: str | None = None  # why nothing was derived

    @property
    def speeds(self) -> tuple[Quantity, ...]:
        return tuple(step.speed for step in self.steps if step.speed is not None)


def bass2_flow_speed(air_display: float) -> Quantity:
    """Estimated centerline flow speed for one BASS-II "Air display" reading."""
    if not BASS2_AIR_DISPLAY_MIN <= air_display <= BASS2_AIR_DISPLAY_MAX:
        raise InvalidMeasurementError(
            f"Air display {air_display:g} is outside the calibrated range "
            f"{BASS2_AIR_DISPLAY_MIN:g}-{BASS2_AIR_DISPLAY_MAX:g}; the speed is not derived"
        )
    return Quantity(round(BASS2_AIR_DISPLAY_FACTOR * air_display, 4), "cm/s")


def derive_bass2_flow(air_display_cell: str) -> FlowDerivation:
    """Interpret the raw "Air display" cell of a PSI-25 table row.

    Only cells made entirely of numbers are converted. A cell with any other word is left
    alone: guessing what "max", "low" or "0.5 pot" means would be inventing data.
    """
    cell = air_display_cell.strip()
    if not cell:
        return FlowDerivation(FlowDerivationKind.NOT_DERIVABLE, reason="no Air display recorded")
    tokens = cell.replace(",", " ").split()
    if not all(_NUMBER.fullmatch(token) for token in tokens):
        return FlowDerivation(
            FlowDerivationKind.NOT_DERIVABLE,
            reason=f"free-text Air display needs human review: {cell!r}",
        )
    steps = tuple(_step(float(token)) for token in tokens)
    if not any(step.speed is not None for step in steps):
        return FlowDerivation(
            FlowDerivationKind.NOT_DERIVABLE,
            steps=steps,
            reason="every reading is outside the calibrated range",
        )
    kind = FlowDerivationKind.SINGLE if len(steps) == 1 else FlowDerivationKind.STEPPED
    return FlowDerivation(kind, steps=steps)


def _step(reading: float) -> FlowStep:
    try:
        return FlowStep(reading, bass2_flow_speed(reading))
    except InvalidMeasurementError:
        return FlowStep(reading, None, note="outside calibrated range")
