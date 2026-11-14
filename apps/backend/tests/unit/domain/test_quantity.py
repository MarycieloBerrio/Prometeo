import pytest

from prometeo.domain.shared.errors import UnitError
from prometeo.domain.shared.quantity import Quantity


def test_converts_within_dimension() -> None:
    assert Quantity(5, "cm/s").to("mm/s").value == pytest.approx(50)
    assert Quantity(21, "%").to("fraction").value == pytest.approx(0.21)


def test_rejects_cross_dimension_conversion() -> None:
    with pytest.raises(UnitError):
        Quantity(1, "mm").to("s")


def test_rejects_unknown_unit() -> None:
    with pytest.raises(UnitError):
        Quantity(1, "furlong")


def test_is_close_uses_relative_tolerance() -> None:
    assert Quantity(21, "%").is_close(Quantity(0.212, "fraction"), rel_tol=0.05)
    assert not Quantity(21, "%").is_close(Quantity(0.30, "fraction"), rel_tol=0.05)
