from unittest.mock import patch

import pytest

from investigraph.sources.fx_rate.adapter import fetch_fx_rate
from investigraph.template.models import Currency


class _FakeTicker:
    def __init__(self, last_price):
        self.fast_info = {"lastPrice": last_price}


def _fetch(last_price, from_=Currency.USD, to=Currency.ILS):
    requested: list[str] = []

    def fake_ticker(symbol):
        requested.append(symbol)
        return _FakeTicker(last_price)

    with patch("investigraph.sources.fx_rate.adapter.yf.Ticker", fake_ticker):
        return fetch_fx_rate(from_, to), requested


def test_returns_target_units_per_one_source_unit_using_yahoo_pair_symbol():
    rate, requested = _fetch(3.2045)

    assert rate == pytest.approx(3.2045)
    assert requested == ["USDILS=X"]


def test_reversed_pair_requests_the_reversed_symbol():
    _, requested = _fetch(0.31, from_=Currency.ILS, to=Currency.USD)

    assert requested == ["ILSUSD=X"]


@pytest.mark.parametrize("bad", [None, 0, -1.5, float("nan"), float("inf")])
def test_unusable_rate_degrades_to_none(bad):
    rate, _ = _fetch(bad)

    assert rate is None


def test_any_yfinance_failure_degrades_to_none():
    def boom(_symbol):
        raise RuntimeError("network down")

    with patch("investigraph.sources.fx_rate.adapter.yf.Ticker", boom):
        assert fetch_fx_rate(Currency.USD, Currency.ILS) is None
