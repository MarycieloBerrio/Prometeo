import pytest

from prometeo.domain.physics.fan_calibration import (
    BASS2_FLOW_METHOD,
    FlowDerivationKind,
    bass2_flow_speed,
    derive_bass2_flow,
)
from prometeo.domain.shared.errors import InvalidMeasurementError
from prometeo.domain.shared.quantity import Quantity


def test_flow_speed_uses_the_calibration_factor_and_carries_units() -> None:
    # Same rows as NASA's calibration sheet: Air display 29 -> 29.1914, 6 -> 6.0396 cm/s.
    assert bass2_flow_speed(29) == Quantity(29.1914, "cm/s")
    assert bass2_flow_speed(6) == Quantity(6.0396, "cm/s")


@pytest.mark.parametrize("reading", [0, 1, 1.9, 59.1, 233, -3])
def test_readings_outside_the_calibrated_range_are_refused(reading: float) -> None:
    with pytest.raises(InvalidMeasurementError):
        bass2_flow_speed(reading)


@pytest.mark.parametrize("reading", [2, 59])
def test_range_limits_are_inclusive(reading: float) -> None:
    assert bass2_flow_speed(reading).unit == "cm/s"


def test_a_single_reading_gives_one_speed() -> None:
    result = derive_bass2_flow(" 5 ")
    assert result.kind is FlowDerivationKind.SINGLE
    assert result.speeds == (Quantity(5.033, "cm/s"),)
    assert result.reason is None


def test_a_numeric_sequence_is_a_stepped_test_with_one_speed_per_step() -> None:
    result = derive_bass2_flow("10   5  4.5  1")
    assert result.kind is FlowDerivationKind.STEPPED
    assert [s.air_display for s in result.steps] == [10, 5, 4.5, 1]
    assert [s.speed.value if s.speed else None for s in result.steps] == [
        10.066,
        5.033,
        4.5297,
        None,  # 1 is below the calibrated range: reported, not converted
    ]
    assert result.steps[-1].note == "outside calibrated range"
    assert len(result.speeds) == 3


def test_commas_are_accepted_as_separators() -> None:
    assert derive_bass2_flow("10,8").kind is FlowDerivationKind.STEPPED


@pytest.mark.parametrize(
    "cell",
    ["10   blowoff", "5 down to ext", "3  0.5 pot   0.4 pot", "2   <1", "see fan", "5>7"],
)
def test_free_text_is_never_interpreted(cell: str) -> None:
    result = derive_bass2_flow(cell)
    assert result.kind is FlowDerivationKind.NOT_DERIVABLE
    assert result.speeds == ()
    assert result.reason is not None and "human review" in result.reason


def test_blank_and_zero_readings_are_not_derivable() -> None:
    assert derive_bass2_flow("").reason == "no Air display recorded"
    zero = derive_bass2_flow("0")
    assert zero.kind is FlowDerivationKind.NOT_DERIVABLE
    assert zero.reason == "every reading is outside the calibrated range"


def test_method_names_the_source_file_and_says_it_is_an_estimate() -> None:
    assert "Fan calibration data.xlsx" in BASS2_FLOW_METHOD
    assert "PSI-25" in BASS2_FLOW_METHOD
    assert "Estimate" in BASS2_FLOW_METHOD
