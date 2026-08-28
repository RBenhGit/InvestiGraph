import json
from pathlib import Path
from unittest.mock import patch

import pytest
import requests

from financial_charts.sources.base import (
    MissingCredentials,
    SourceUnavailable,
    TickerNotFound,
)
from financial_charts.sources.ranges import RANGES
from financial_charts.sources.twelvedata.adapter import TwelveDataAdapter, _price_params
from financial_charts.template.models import Currency, Market, Period

_FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((_FIXTURES / f"{name}.json").read_text())


def _fetch_with_fixture(
    fixture_name: str, ticker: str, market: Market, period: Period, range: str
):
    fixture = _load(fixture_name)
    responses = {
        "time_series": fixture["price"],
        "income_statement": fixture["income"],
        "cash_flow": fixture["cashflow"],
        "balance_sheet": fixture["balance_sheet"],
    }

    def fake_get(self, endpoint: str, **params) -> dict:
        return responses[endpoint]

    with (
        patch(
            "financial_charts.sources.twelvedata.adapter.TwelveDataAdapter._get",
            fake_get,
        ),
        patch.dict("os.environ", {"TWELVEDATA_API_KEY": "test-key"}),
    ):
        return TwelveDataAdapter().fetch(ticker, market, period, range)


def test_us_ticker_maps_price_and_fundamentals_in_usd():
    fundamentals = _fetch_with_fixture("aapl", "AAPL", Market.US, Period.ANNUAL, "5y")

    assert fundamentals.currency == Currency.USD
    assert fundamentals.series["price"].available
    assert fundamentals.series["price"].points[0].value.currency == Currency.USD

    revenue = fundamentals.series["revenue"]
    assert revenue.available
    assert revenue.points[0].value.value > 0

    assert fundamentals.series["eps"].available
    assert fundamentals.series["gross_margin"].available

    assert fundamentals.series["ebitda"].available
    assert fundamentals.series["research_and_development"].available
    assert fundamentals.series["selling_general_administrative"].available
    assert fundamentals.series["shares_outstanding"].available
    assert fundamentals.series["shares_outstanding"].points[0].value > 0

    dividends = fundamentals.series["dividends_paid"]
    assert dividends.available
    # Twelve Data reports dividend cash outflows as negative; the adapter
    # normalizes to a positive "amount paid out" for the chart.
    assert all(p.value.value > 0 for p in dividends.points)

    assert fundamentals.series["ebit"].available
    assert fundamentals.series["total_assets"].available
    assert fundamentals.series["total_liabilities"].available
    assert fundamentals.series["total_equity"].available
    assert fundamentals.series["cash_and_equivalents"].available
    assert fundamentals.series["total_debt"].available
    assert fundamentals.series["total_current_assets"].available
    assert fundamentals.series["total_current_liabilities"].available


def test_tase_ticker_converts_agorot_price_and_flags_missing_gross_margin():
    fundamentals = _fetch_with_fixture(
        "lumi_ta", "LUMI.TA", Market.TASE, Period.ANNUAL, "5y"
    )

    assert fundamentals.currency == Currency.ILS

    price = fundamentals.series["price"]
    assert price.available
    assert price.points[0].value.currency == Currency.ILS

    raw = _load("lumi_ta")
    expected_shekels = float(raw["price"]["values"][-1]["close"]) / 100
    assert price.points[0].value.value == pytest.approx(expected_shekels)

    assert not fundamentals.series["gross_margin"].available
    assert any("gross_margin" in limit for limit in fundamentals.source_limits)

    # This fixture's income statement has ebitda/ebit/R&D as null — must
    # degrade to unavailable, not crash.
    assert not fundamentals.series["ebitda"].available
    assert not fundamentals.series["research_and_development"].available
    assert fundamentals.series["selling_general_administrative"].available

    # A bank's balance sheet has no current/non-current split — must degrade
    # to unavailable, not crash. Total debt is still derivable from long-term
    # debt alone even though short-term debt is null here.
    assert not fundamentals.series["total_current_assets"].available
    assert not fundamentals.series["total_current_liabilities"].available
    assert fundamentals.series["total_assets"].available
    assert fundamentals.series["total_equity"].available
    assert fundamentals.series["total_debt"].available


def test_unknown_ticker_raises_ticker_not_found():
    def fake_get(self, endpoint: str, **params) -> dict:
        raise TickerNotFound(params.get("symbol", ""))

    with (
        patch(
            "financial_charts.sources.twelvedata.adapter.TwelveDataAdapter._get",
            fake_get,
        ),
        patch.dict("os.environ", {"TWELVEDATA_API_KEY": "test-key"}),
    ):
        with pytest.raises(TickerNotFound):
            TwelveDataAdapter().fetch("ZZZZZZINVALID", Market.US, Period.ANNUAL, "1y")


def test_missing_api_key_raises_missing_credentials():
    with (
        patch("financial_charts.sources.twelvedata.adapter.load_dotenv"),
        patch.dict("os.environ", {}, clear=True),
    ):
        with pytest.raises(MissingCredentials):
            TwelveDataAdapter()


def test_declares_capability():
    with patch.dict("os.environ", {"TWELVEDATA_API_KEY": "test-key"}):
        capability = TwelveDataAdapter().capability()
    assert Market.US in capability.markets
    assert Market.TASE in capability.markets
    assert capability.max_history[Period.ANNUAL] == 10


def test_transport_failure_raises_source_unavailable():
    with (
        patch(
            "financial_charts.sources.twelvedata.adapter.requests.get",
            side_effect=requests.ConnectionError("network is down"),
        ),
        patch.dict("os.environ", {"TWELVEDATA_API_KEY": "test-key"}),
    ):
        with pytest.raises(SourceUnavailable):
            TwelveDataAdapter().fetch("AAPL", Market.US, Period.ANNUAL, "1y")


def test_income_row_missing_fiscal_date_is_skipped_not_a_crash():
    fixture = _load("aapl")
    malformed_row = {k: v for k, v in fixture["income"]["income_statement"][0].items()}
    del malformed_row["fiscal_date"]
    responses = {
        "time_series": fixture["price"],
        "income_statement": {
            "income_statement": [
                malformed_row,
                *fixture["income"]["income_statement"][1:],
            ],
            "meta": fixture["income"]["meta"],
        },
        "cash_flow": fixture["cashflow"],
        "balance_sheet": fixture["balance_sheet"],
    }

    def fake_get(self, endpoint: str, **params) -> dict:
        return responses[endpoint]

    with (
        patch(
            "financial_charts.sources.twelvedata.adapter.TwelveDataAdapter._get",
            fake_get,
        ),
        patch.dict("os.environ", {"TWELVEDATA_API_KEY": "test-key"}),
    ):
        fundamentals = TwelveDataAdapter().fetch("AAPL", Market.US, Period.ANNUAL, "5y")

    revenue = fundamentals.series["revenue"]
    assert revenue.available
    assert len(revenue.points) == len(fixture["income"]["income_statement"]) - 1


def test_every_range_asks_for_daily_bars():
    """The price chart's SMA windows count points, not days, so a coarser bar at long
    ranges would quietly turn "SMA 50" into a 50-week or 50-month average — and put this
    source at odds with yfinance, which is always daily, on the same chart.
    """
    for range_ in RANGES:
        params = _price_params(range_)
        assert params["interval"] == "1day", range_
        # 5000 is Twelve Data's documented (and live-verified) outputsize cap.
        assert 0 < params["outputsize"] <= 5000, range_

    # Enough bars for the widest SMA window once the range is long enough to want it.
    assert _price_params("3y")["outputsize"] >= 200


def test_unknown_range_still_asks_for_daily_bars():
    assert _price_params("nonsense") == {"interval": "1day", "outputsize": 5000}


def test_price_params_reach_the_time_series_request():
    fixture = _load("aapl")
    responses = {
        "time_series": fixture["price"],
        "income_statement": fixture["income"],
        "cash_flow": fixture["cashflow"],
        "balance_sheet": fixture["balance_sheet"],
    }
    seen: dict[str, dict] = {}

    def fake_get(self, endpoint: str, **params) -> dict:
        seen[endpoint] = params
        return responses[endpoint]

    with (
        patch(
            "financial_charts.sources.twelvedata.adapter.TwelveDataAdapter._get",
            fake_get,
        ),
        patch.dict("os.environ", {"TWELVEDATA_API_KEY": "test-key"}),
    ):
        TwelveDataAdapter().fetch("AAPL", Market.US, Period.ANNUAL, "10y")

    assert seen["time_series"]["interval"] == "1day"
    assert seen["time_series"]["outputsize"] == 2600
    # The statement endpoints take no range/date param — range bounds prices only.
    assert "interval" not in seen["income_statement"]
