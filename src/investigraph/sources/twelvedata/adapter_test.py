import json
from pathlib import Path
from unittest.mock import patch

import pytest
import requests

from investigraph.sources.base import (
    MissingCredentials,
    SourceUnavailable,
    TickerNotFound,
)
from investigraph.sources.ranges import RANGES
from investigraph.sources.twelvedata.adapter import (
    TwelveDataAdapter,
    _price_params,
    _price_series,
)
from investigraph.template.models import Currency, Market, Period

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
            "investigraph.sources.twelvedata.adapter.TwelveDataAdapter._get",
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
            "investigraph.sources.twelvedata.adapter.TwelveDataAdapter._get",
            fake_get,
        ),
        patch.dict("os.environ", {"TWELVEDATA_API_KEY": "test-key"}),
    ):
        with pytest.raises(TickerNotFound):
            TwelveDataAdapter().fetch("ZZZZZZINVALID", Market.US, Period.ANNUAL, "1y")


def test_missing_api_key_raises_missing_credentials():
    with (
        patch("investigraph.sources.twelvedata.adapter.load_dotenv"),
        patch.dict("os.environ", {}, clear=True),
    ):
        with pytest.raises(MissingCredentials):
            TwelveDataAdapter()


def test_declares_capability():
    with patch.dict("os.environ", {"TWELVEDATA_API_KEY": "test-key"}):
        capability = TwelveDataAdapter().capability()
    assert Market.US in capability.markets
    assert Market.TASE in capability.markets
    assert capability.max_history[Period.ANNUAL] == 6
    # TTM is derived (template/trailing.py's derive_ttm_fundamentals), not native.
    assert Period.TTM in capability.periods
    # TTM history reaches as far back as the annual series (fiscal-year-end points), not just
    # as far as the few quarters the source returns.
    assert capability.max_history[Period.TTM] == capability.max_history[Period.ANNUAL]
    assert capability.max_history[Period.TTM] > capability.max_history[Period.QUARTERLY]


def test_transport_failure_raises_source_unavailable():
    with (
        patch(
            "investigraph.sources.twelvedata.adapter.requests.get",
            side_effect=requests.ConnectionError("network is down"),
        ),
        patch.dict("os.environ", {"TWELVEDATA_API_KEY": "test-key"}),
    ):
        with pytest.raises(SourceUnavailable):
            TwelveDataAdapter().fetch("AAPL", Market.US, Period.ANNUAL, "1y")


def _mock_response(payload: dict):
    from unittest.mock import Mock

    response = Mock()
    response.json.return_value = payload
    return response


def test_rate_limit_retries_with_backoff_then_succeeds():
    fixture = _load("aapl")
    success_by_endpoint = {
        "time_series": fixture["price"],
        "income_statement": fixture["income"],
        "cash_flow": fixture["cashflow"],
        "balance_sheet": fixture["balance_sheet"],
    }
    rate_limited = _mock_response(
        {"status": "error", "code": 429, "message": "You have run out of API credits"}
    )

    call_count = {"n": 0}

    def fake_requests_get(url, params, timeout):
        # Every endpoint's very first attempt is rate-limited; the retry succeeds.
        call_count["n"] += 1
        endpoint = url.rsplit("/", 1)[-1]
        if call_count["n"] <= 1:
            return rate_limited
        return _mock_response(success_by_endpoint[endpoint])

    with (
        patch(
            "investigraph.sources.twelvedata.adapter.requests.get",
            side_effect=fake_requests_get,
        ),
        patch("investigraph.sources.twelvedata.adapter.time.sleep") as mock_sleep,
        patch.dict("os.environ", {"TWELVEDATA_API_KEY": "test-key"}),
    ):
        fundamentals = TwelveDataAdapter().fetch("AAPL", Market.US, Period.ANNUAL, "5y")

    assert fundamentals.series["price"].available
    mock_sleep.assert_called_once_with(2)


def test_rate_limit_exhausts_retries_and_raises_source_unavailable():
    rate_limited = _mock_response(
        {"status": "error", "code": 429, "message": "You have run out of API credits"}
    )

    with (
        patch(
            "investigraph.sources.twelvedata.adapter.requests.get",
            return_value=rate_limited,
        ),
        patch("investigraph.sources.twelvedata.adapter.time.sleep") as mock_sleep,
        patch.dict("os.environ", {"TWELVEDATA_API_KEY": "test-key"}),
    ):
        with pytest.raises(SourceUnavailable, match="API credits"):
            TwelveDataAdapter().fetch("AAPL", Market.US, Period.ANNUAL, "1y")

    # 3 retries -> 3 sleeps, using the full backoff schedule, before giving up.
    assert mock_sleep.call_args_list == [((2,),), ((5,),), ((10,),)]


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
            "investigraph.sources.twelvedata.adapter.TwelveDataAdapter._get",
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
            "investigraph.sources.twelvedata.adapter.TwelveDataAdapter._get",
            fake_get,
        ),
        patch.dict("os.environ", {"TWELVEDATA_API_KEY": "test-key"}),
    ):
        TwelveDataAdapter().fetch("AAPL", Market.US, Period.ANNUAL, "10y")

    assert seen["time_series"]["interval"] == "1day"
    assert seen["time_series"]["outputsize"] == 2600
    # The statement endpoints take no range/date param — range bounds prices only.
    assert "interval" not in seen["income_statement"]


def test_fetch_ttm_derives_from_a_quarterly_fetch():
    # The actual trailing-four-quarters math is covered by
    # template/trailing_test.py's derive_ttm_fundamentals tests; this only
    # confirms the adapter wires a TTM request through a QUARTERLY fetch
    # into that function, rather than trying to fetch TTM natively.
    sentinel = object()
    with patch(
        "investigraph.sources.twelvedata.adapter.derive_ttm_fundamentals",
        return_value=sentinel,
    ) as mock_derive:
        result = _fetch_with_fixture("aapl", "AAPL", Market.US, Period.TTM, "5y")

    assert result is sentinel
    mock_derive.assert_called_once()
    (quarterly_arg,), _ = mock_derive.call_args
    assert quarterly_arg.period == Period.QUARTERLY


def test_fetch_ttm_hands_derive_a_loader_that_fetches_the_annual_series():
    # The annual series is only used to reconstruct a missing quarter; the loader is
    # lazy so a ticker with complete quarters never pays for the extra fetch.
    with patch(
        "investigraph.sources.twelvedata.adapter.derive_ttm_fundamentals",
        return_value=object(),
    ) as mock_derive:
        _fetch_with_fixture("aapl", "AAPL", Market.US, Period.TTM, "5y")

    loader = mock_derive.call_args.kwargs["annual_loader"]
    with patch.object(TwelveDataAdapter, "fetch", return_value="annual") as fetch:
        assert loader() == "annual"
    assert fetch.call_args.args[2] == Period.ANNUAL


def test_ttm_annual_loader_degrades_to_none_when_the_source_is_unavailable():
    with patch(
        "investigraph.sources.twelvedata.adapter.derive_ttm_fundamentals",
        return_value=object(),
    ) as mock_derive:
        _fetch_with_fixture("aapl", "AAPL", Market.US, Period.TTM, "5y")

    loader = mock_derive.call_args.kwargs["annual_loader"]
    with patch.object(
        TwelveDataAdapter, "fetch", side_effect=SourceUnavailable("down")
    ):
        assert loader() is None


# QLTU.TA, as the API really returned it: the series is labelled ILA (agorot) and every bar is in
# agorot except 2025-06-19, which arrives already in shekels (note the decimals). Divided by
# 100 like the rest, that one bar became 3.59 and dipped the P/E line to ~0.3 for a day.
_QLTU_ROWS = [  # newest first, like the API
    {"datetime": "2025-06-23", "close": "35680"},
    {"datetime": "2025-06-22", "close": "35900"},
    {"datetime": "2025-06-19", "close": "359"},
    {"datetime": "2025-06-18", "close": "34270"},
    {"datetime": "2025-06-17", "close": "35390"},
]


def _price_json(rows, currency="ILA"):
    return {"meta": {"currency": currency}, "values": rows}


def _closes(series):
    return {str(p.date): p.value.value for p in series.points}


def test_a_bar_returned_in_shekels_inside_an_agorot_series_is_not_divided_again():
    limits: list[str] = []

    closes = _closes(_price_series(_price_json(_QLTU_ROWS), limits))

    assert closes["2025-06-19"] == pytest.approx(359.0)
    # Every other bar is still agorot -> shekels.
    assert closes["2025-06-18"] == pytest.approx(342.70)
    assert closes["2025-06-22"] == pytest.approx(359.0)


def test_the_unit_correction_is_disclosed_with_its_date():
    limits: list[str] = []

    _price_series(_price_json(_QLTU_ROWS), limits)

    note = next(limit for limit in limits if "price" in limit)
    assert "2025-06-19" in note and "100x" in note


def test_a_clean_agorot_series_is_just_divided_by_100_with_no_note():
    clean = [r for r in _QLTU_ROWS if r["datetime"] != "2025-06-19"]
    limits: list[str] = []

    closes = _closes(_price_series(_price_json(clean), limits))

    assert closes["2025-06-18"] == pytest.approx(342.70)
    assert limits == []


def test_a_real_large_one_day_move_is_not_mistaken_for_a_unit_error():
    # A genuine -60% day is nowhere near the exact ~100x gap of a unit mix-up.
    rows = [dict(r) for r in _QLTU_ROWS]
    rows[2] = {"datetime": "2025-06-19", "close": "14000"}  # 140 shekels vs ~350
    limits: list[str] = []

    closes = _closes(_price_series(_price_json(rows), limits))

    assert closes["2025-06-19"] == pytest.approx(140.0)
    assert limits == []


def test_a_non_agorot_series_is_never_touched():
    rows = [
        {"datetime": "2025-06-19", "close": "3.5"},
        {"datetime": "2025-06-18", "close": "350"},
        {"datetime": "2025-06-17", "close": "351"},
    ]
    limits: list[str] = []

    closes = _closes(_price_series(_price_json(rows, currency="USD"), limits))

    assert closes["2025-06-19"] == 3.5
    assert limits == []


def test_a_bar_100x_too_high_inside_an_agorot_series_is_rescaled_down():
    # TEVA.TA 2010-03-28 as the API returned it: 2380000 between 23920 and 23650 (the other
    # direction of the same unit mix-up).
    rows = [
        {"datetime": "2010-03-31", "close": "23650"},
        {"datetime": "2010-03-28", "close": "2380000"},
        {"datetime": "2010-03-25", "close": "23920"},
        {"datetime": "2010-03-24", "close": "23800"},
        {"datetime": "2010-03-23", "close": "23700"},
    ]
    limits: list[str] = []

    closes = _closes(_price_series(_price_json(rows), limits))

    assert closes["2010-03-28"] == pytest.approx(238.0)
    assert closes["2010-03-25"] == pytest.approx(239.20)
    assert any("2010-03-28" in limit and "100x" in limit for limit in limits)
