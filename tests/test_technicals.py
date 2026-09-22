import pytest

from investment_research.analysis.technicals import (
    daily_returns,
    maximum_drawdown,
    moving_average,
)


def test_moving_average_waits_for_a_complete_window() -> None:
    assert moving_average([10, 20, 30, 40], 3) == [None, None, 20.0, 30.0]


def test_moving_average_rejects_invalid_window() -> None:
    with pytest.raises(ValueError, match="greater than zero"):
        moving_average([10, 20], 0)


def test_daily_returns_calculates_period_changes() -> None:
    assert daily_returns([100, 110, 99]) == pytest.approx([0.1, -0.1])


def test_maximum_drawdown_returns_largest_peak_to_trough_loss() -> None:
    assert maximum_drawdown([100, 120, 90, 110]) == pytest.approx(-0.25)