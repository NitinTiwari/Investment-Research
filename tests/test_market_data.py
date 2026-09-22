import pytest

from investment_research.data.market_data import normalize_ticker


def test_normalize_ticker_strips_and_uppercases() -> None:
    assert normalize_ticker("  aapl ") == "AAPL"


def test_normalize_ticker_rejects_empty_input() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        normalize_ticker("  ")