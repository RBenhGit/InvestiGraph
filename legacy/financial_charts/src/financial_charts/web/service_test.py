from datetime import date
from unittest.mock import patch

import pytest

from financial_charts.sources.base import Capability, SourceUnavailable, TickerNotFound
from financial_charts.template.models import (
    CompanyFundamentals,
    Currency,
    Market,
    MetricSeries,
    Money,
    Period,
    Point,
    Unit,
)
from financial_charts.web import service


def _fundamentals(ticker: str = "AAPL") -> CompanyFundamentals:
    return CompanyFundamentals(
        ticker=ticker,
        market=Market.US,
        currency=Currency.USD,
        period=Period.ANNUAL,
        range="10y",
        series={
            "price": MetricSeries(
                metric_id="price",
                points=[
                    Point(
                        date=date(2026, 1, 1),
                        value=Money(value=100, currency=Currency.USD, scale=Unit.ONES),
                    )
                ],
                available=True,
            )
        },
    )


class _StubAdapter:
    def __init__(self, fundamentals=None, fetch_error=None):
        self._fundamentals = fundamentals or _fundamentals()
        self._fetch_error = fetch_error
        self.fetch_calls = 0

    def capability(self) -> Capability:
        return Capability(
            markets={Market.US},
            periods={Period.ANNUAL},
            max_history={Period.ANNUAL: 4},
            metrics={"price"},
        )

    def fetch(self, ticker, market, period, range_) -> CompanyFundamentals:
        self.fetch_calls += 1
        if self._fetch_error:
            raise self._fetch_error
        return self._fundamentals


def test_load_fundamentals_merges_capability_limits(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with patch("financial_charts.web.service.get_source", return_value=_StubAdapter()):
        fundamentals = service.load_fundamentals(
            "AAPL", "yfinance", Period.ANNUAL, "10y"
        )

    # Declared 4y annual history vs a 10y request → a merged source limit.
    assert any("10y" in limit and "4y" in limit for limit in fundamentals.source_limits)


def test_load_fundamentals_is_cache_first(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    adapter = _StubAdapter()
    with patch("financial_charts.web.service.get_source", return_value=adapter):
        service.load_fundamentals("AAPL", "yfinance", Period.ANNUAL, "10y")
        service.load_fundamentals("AAPL", "yfinance", Period.ANNUAL, "10y")

    assert adapter.fetch_calls == 1


def test_capability_limits_are_merged_even_on_a_cache_hit(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    adapter = _StubAdapter()
    with patch("financial_charts.web.service.get_source", return_value=adapter):
        service.load_fundamentals(
            "AAPL", "yfinance", Period.ANNUAL, "10y"
        )  # populate cache
        cached = service.load_fundamentals("AAPL", "yfinance", Period.ANNUAL, "10y")

    assert adapter.fetch_calls == 1  # served from cache
    assert any("10y" in limit and "4y" in limit for limit in cached.source_limits)


def test_load_fundamentals_propagates_ticker_not_found(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    adapter = _StubAdapter(fetch_error=TickerNotFound("ZZZ"))
    with patch("financial_charts.web.service.get_source", return_value=adapter):
        with pytest.raises(TickerNotFound):
            service.load_fundamentals("ZZZ", "yfinance", Period.ANNUAL, "10y")


def test_load_fundamentals_falls_back_to_stale_cache_on_source_unavailable(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)

    # Seed a cache entry via a successful load, then a later fetch fails.
    good_adapter = _StubAdapter()
    with patch("financial_charts.web.service.get_source", return_value=good_adapter):
        service.load_fundamentals("AAPL", "yfinance", Period.ANNUAL, "10y")

    failing_adapter = _StubAdapter(fetch_error=SourceUnavailable("boom"))
    with (
        patch("financial_charts.web.service.get_source", return_value=failing_adapter),
        patch("financial_charts.web.service.date") as fake_date,
    ):
        fake_date.today.return_value = date(2030, 1, 1)  # miss today's key, force fetch
        fundamentals = service.load_fundamentals(
            "AAPL", "yfinance", Period.ANNUAL, "10y"
        )

    assert any("stale" in limit for limit in fundamentals.source_limits)
