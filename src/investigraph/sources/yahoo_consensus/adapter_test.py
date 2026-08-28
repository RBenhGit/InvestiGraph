import json
from datetime import date
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from investigraph.sources.yahoo_consensus.adapter import fetch_analyst_consensus

_FIXTURES = Path(__file__).parent / "fixtures"


class _FakeTicker:
    """Stands in for `yfinance.Ticker`, serving a recorded fixture instead of the network."""

    def __init__(self, fixture_name: str):
        raw = json.loads((_FIXTURES / f"{fixture_name}.json").read_text())
        self.info = raw["info"]
        self._growth_estimates = pd.read_json(
            StringIO(raw["growth_estimates"]), orient="split"
        )
        self._financials = pd.read_json(StringIO(raw["financials"]), orient="split")

    @property
    def growth_estimates(self) -> pd.DataFrame:
        return self._growth_estimates

    @property
    def financials(self) -> pd.DataFrame:
        return self._financials


def _fetch_with_fixture(fixture_name: str, ticker: str = "TICK"):
    with patch(
        "investigraph.sources.yahoo_consensus.adapter.yf.Ticker",
        lambda _ticker: _FakeTicker(fixture_name),
    ):
        return fetch_analyst_consensus(ticker)


def test_maps_the_full_field_set_from_a_healthy_ticker():
    consensus = _fetch_with_fixture("aapl", "AAPL")

    assert consensus is not None
    assert consensus.ticker == "AAPL"
    assert consensus.next_year_eps_growth_percent == pytest.approx(8.09)
    assert consensus.price_target.mean == pytest.approx(324.45282)
    assert consensus.price_target.high == pytest.approx(400.0)
    assert consensus.price_target.low == pytest.approx(215.0)
    assert consensus.price_target.number_of_analysts == 39
    assert consensus.recommendation_key == "buy"
    assert consensus.beta == pytest.approx(1.086)
    assert consensus.price_to_sales == pytest.approx(10.024735)
    assert consensus.trailing_eps == pytest.approx(8.71)
    assert consensus.most_recent_quarter_end_date == date(2026, 6, 27)
    # (416_161_000_000 / 391_035_000_000 - 1 + 0.35979) * 100
    assert consensus.rule_of_40 == pytest.approx(
        (416_161_000_000 / 391_035_000_000 - 1 + 0.35979) * 100
    )


def test_recommendation_key_of_literal_none_string_is_passed_through_not_treated_as_missing():
    # Yahoo returns the literal string "none" (not Python None) for a ticker with no
    # analyst recommendation on file — confirmed live on MS. A UI checking `is not
    # None` must see this string, not a null.
    consensus = _fetch_with_fixture("bank_no_ebitda", "MS")

    assert consensus is not None
    assert consensus.recommendation_key == "none"


def test_ebitda_margin_of_zero_with_no_raw_ebitda_is_untrustworthy_rule_of_40_is_none():
    # A bank: ebitdaMargins reports a literal 0 because EBITDA isn't a tracked concept
    # for it at all (ebitda itself is missing), not because it's genuinely breakeven.
    consensus = _fetch_with_fixture("bank_no_ebitda", "MS")

    assert consensus is not None
    assert consensus.rule_of_40 is None


def test_ebitda_margin_of_zero_with_negative_raw_ebitda_is_untrustworthy_rule_of_40_is_none():
    # IONQ: ebitda is a real, large negative number (~-$793M on ~$130M revenue) yet
    # ebitdaMargins still reports a literal 0 — trusting that 0 would previously have
    # fabricated a "good" Rule of 40 score for a company burning cash.
    consensus = _fetch_with_fixture("negative_ebitda", "IONQ")

    assert consensus is not None
    assert consensus.rule_of_40 is None
    assert consensus.trailing_eps == pytest.approx(-3.87)


def test_rule_of_40_uses_annual_revenue_growth_not_the_mismatched_quarterly_figure():
    # NVDA: info["revenueGrowth"] (quarterly YoY) is 105.9%, wildly different from the
    # true annual growth (~65.47%) computed from the two most recent `financials`
    # columns. rule_of_40 must be built from the annual figure only.
    consensus = _fetch_with_fixture("nvda_accelerating", "NVDA")

    assert consensus is not None
    annual_growth = 215_938_000_000 / 130_497_000_000 - 1
    assert annual_growth == pytest.approx(0.6547, abs=1e-3)
    expected_rule_of_40 = (annual_growth + 0.66431) * 100
    assert consensus.rule_of_40 == pytest.approx(expected_rule_of_40)
    # Sanity: the quarterly figure would have produced a very different number —
    # asserting our result is nowhere near it guards against silently reintroducing
    # the mismatched-period bug.
    quarterly_based = (1.059 + 0.66431) * 100
    assert consensus.rule_of_40 != pytest.approx(quarterly_based)


def test_ticker_with_no_analyst_coverage_degrades_fields_to_none_not_a_failure():
    consensus = _fetch_with_fixture("no_coverage", "SPY")

    assert consensus is not None
    assert consensus.ticker == "SPY"
    assert consensus.next_year_eps_growth_percent is None
    assert consensus.price_target.mean is None
    assert consensus.price_target.number_of_analysts is None
    assert consensus.recommendation_key is None
    assert consensus.rule_of_40 is None
    assert consensus.trailing_eps is None
    assert consensus.most_recent_quarter_end_date is None


def test_unknown_ticker_degrades_to_none_rather_than_raising():
    class _EmptyTicker:
        info = {"trailingPegRatio": None}

    with patch(
        "investigraph.sources.yahoo_consensus.adapter.yf.Ticker",
        lambda _ticker: _EmptyTicker(),
    ):
        assert fetch_analyst_consensus("ZZZZZZINVALID") is None


def test_network_failure_degrades_to_none_rather_than_raising():
    class _BrokenTicker:
        @property
        def info(self):
            raise ConnectionError("network is down")

    with patch(
        "investigraph.sources.yahoo_consensus.adapter.yf.Ticker",
        lambda _ticker: _BrokenTicker(),
    ):
        assert fetch_analyst_consensus("AAPL") is None


def test_growth_estimates_failure_degrades_only_that_field_not_the_whole_fetch():
    class _PartiallyBrokenTicker(_FakeTicker):
        @property
        def growth_estimates(self):
            raise ConnectionError("growth_estimates endpoint down")

    def _make(_ticker):
        return _PartiallyBrokenTicker("aapl")

    with patch("investigraph.sources.yahoo_consensus.adapter.yf.Ticker", _make):
        consensus = fetch_analyst_consensus("AAPL")

    assert consensus is not None
    assert consensus.next_year_eps_growth_percent is None
    # The rest of the fetch still succeeded.
    assert consensus.trailing_eps == pytest.approx(8.71)
