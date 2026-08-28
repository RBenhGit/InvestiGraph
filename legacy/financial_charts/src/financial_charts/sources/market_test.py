from financial_charts.sources.market import is_valid_ticker, market_of, normalize_ticker
from financial_charts.template.models import Market


def test_ta_suffix_routes_to_tase():
    assert market_of("TEVA.TA") == Market.TASE


def test_bare_ticker_routes_to_us():
    assert market_of("AAPL") == Market.US


def test_ta_suffix_is_case_insensitive():
    assert market_of("teva.ta") == Market.TASE


def test_valid_tickers_are_accepted():
    assert is_valid_ticker("AAPL")
    assert is_valid_ticker("TEVA.TA")
    assert is_valid_ticker("BRK-B")


def test_path_traversal_ticker_is_rejected():
    assert not is_valid_ticker("../../etc/passwd")
    assert not is_valid_ticker("../../../tmp/evil")


def test_empty_ticker_is_rejected():
    assert not is_valid_ticker("")


def test_normalize_ticker_uppercases_and_strips():
    assert normalize_ticker("aapl") == "AAPL"
    assert normalize_ticker(" teva.ta ") == "TEVA.TA"
