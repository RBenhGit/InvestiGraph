from datetime import date
from unittest.mock import patch

import pytest

from investigraph.sources.base import Capability, SourceUnavailable, TickerNotFound
from investigraph.template.models import (
    CompanyFundamentals,
    Currency,
    Market,
    MetricSeries,
    Money,
    Period,
    Point,
    Unit,
)
from investigraph.web import service


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
    with patch("investigraph.web.service.get_source", return_value=_StubAdapter()):
        fundamentals = service.load_fundamentals(
            "AAPL", "yfinance", Period.ANNUAL, "10y"
        )

    # Declared 4y annual history vs a 10y request → a merged source limit.
    assert any("10y" in limit and "4y" in limit for limit in fundamentals.source_limits)


def test_load_fundamentals_is_cache_first(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    adapter = _StubAdapter()
    with patch("investigraph.web.service.get_source", return_value=adapter):
        service.load_fundamentals("AAPL", "yfinance", Period.ANNUAL, "10y")
        service.load_fundamentals("AAPL", "yfinance", Period.ANNUAL, "10y")

    assert adapter.fetch_calls == 1


def test_capability_limits_are_merged_even_on_a_cache_hit(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    adapter = _StubAdapter()
    with patch("investigraph.web.service.get_source", return_value=adapter):
        service.load_fundamentals(
            "AAPL", "yfinance", Period.ANNUAL, "10y"
        )  # populate cache
        cached = service.load_fundamentals("AAPL", "yfinance", Period.ANNUAL, "10y")

    assert adapter.fetch_calls == 1  # served from cache
    assert any("10y" in limit and "4y" in limit for limit in cached.source_limits)


def test_load_fundamentals_propagates_ticker_not_found(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    adapter = _StubAdapter(fetch_error=TickerNotFound("ZZZ"))
    with patch("investigraph.web.service.get_source", return_value=adapter):
        with pytest.raises(TickerNotFound):
            service.load_fundamentals("ZZZ", "yfinance", Period.ANNUAL, "10y")


def test_load_fundamentals_falls_back_to_stale_cache_on_source_unavailable(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)

    # Seed a cache entry via a successful load, then a later fetch fails.
    good_adapter = _StubAdapter()
    with patch("investigraph.web.service.get_source", return_value=good_adapter):
        service.load_fundamentals("AAPL", "yfinance", Period.ANNUAL, "10y")

    failing_adapter = _StubAdapter(fetch_error=SourceUnavailable("boom"))
    with (
        patch("investigraph.web.service.get_source", return_value=failing_adapter),
        patch("investigraph.web.service.date") as fake_date,
    ):
        fake_date.today.return_value = date(2030, 1, 1)  # miss today's key, force fetch
        fundamentals = service.load_fundamentals(
            "AAPL", "yfinance", Period.ANNUAL, "10y"
        )

    assert any("stale" in limit for limit in fundamentals.source_limits)


def test_load_fundamentals_attaches_fx_even_on_a_cache_hit(tmp_path, monkeypatch):
    # The FX series is derived per render (not cached), so a cache entry written before
    # this existed still gets it.
    monkeypatch.chdir(tmp_path)
    adapter = _StubAdapter()
    with (
        patch("investigraph.web.service.get_source", return_value=adapter),
        patch("investigraph.web.service.attach_fx_series") as attach,
    ):
        service.load_fundamentals("AAPL", "yfinance", Period.ANNUAL, "10y")
        cached = service.load_fundamentals("AAPL", "yfinance", Period.ANNUAL, "10y")

    assert adapter.fetch_calls == 1
    assert attach.call_count == 2
    attach.assert_called_with(cached)


# --- TTM is composed from the cached QUARTERLY + ANNUAL series --------------------------------


def _with_eps(period: Period, eps: list[tuple[date, float]]) -> CompanyFundamentals:
    base = _fundamentals()
    base.period = period
    base.series["eps"] = MetricSeries(
        metric_id="eps",
        points=[
            Point(
                date=d,
                value=Money(value=v, currency=Currency.USD, scale=Unit.ONES),
            )
            for d, v in eps
        ],
        available=True,
    )
    return base


class _PeriodAdapter:
    """A real adapter hands back the period it was asked for; counts fetches per period."""

    def __init__(self, annual_error: Exception | None = None):
        self.calls: list[Period] = []
        self._annual_error = annual_error

    def capability(self) -> Capability:
        return Capability(
            markets={Market.US},
            periods={Period.ANNUAL, Period.QUARTERLY, Period.TTM},
            # QUARTERLY is shallow on purpose: its range limit must not leak into TTM's notes.
            max_history={Period.ANNUAL: 6, Period.QUARTERLY: 1, Period.TTM: 6},
            metrics={"price", "eps"},
        )

    def fetch(self, ticker, market, period, range_) -> CompanyFundamentals:
        self.calls.append(period)
        if period == Period.TTM:
            raise AssertionError("TTM must be composed, never fetched")
        if period == Period.ANNUAL:
            if self._annual_error:
                raise self._annual_error
            return _with_eps(
                Period.ANNUAL, [(date(2024, 12, 31), 3.0), (date(2025, 12, 31), 4.0)]
            )
        return _with_eps(Period.QUARTERLY, [(d, 1.0) for d in _QUARTER_ENDS])


_QUARTER_ENDS = [
    date(2025, 3, 31),
    date(2025, 6, 30),
    date(2025, 9, 30),
    date(2025, 12, 31),
    date(2026, 3, 31),
]


def _ttm_eps(fundamentals: CompanyFundamentals) -> dict[date, float]:
    return {p.date: p.value.value for p in fundamentals.series["eps"].points}


def test_a_cold_ttm_load_fetches_quarterly_and_annual_once_each_and_never_ttm(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    adapter = _PeriodAdapter()
    with patch("investigraph.web.service.get_source", return_value=adapter):
        result = service.load_fundamentals("AAPL", "twelvedata", Period.TTM, "max")

    assert result.period == Period.TTM
    assert sorted(adapter.calls, key=lambda p: p.value) == [
        Period.ANNUAL,
        Period.QUARTERLY,
    ]
    # Real TTM content, not an empty shell: the rolling sum and the annual year end.
    ttm = _ttm_eps(result)
    assert ttm[date(2025, 12, 31)] == 4.0
    assert date(2024, 12, 31) in ttm


def test_ttm_costs_no_fetch_when_quarterly_and_annual_are_already_cached(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    adapter = _PeriodAdapter()
    with patch("investigraph.web.service.get_source", return_value=adapter):
        # The page's own charts load these two anyway (cache-first).
        service.load_fundamentals("AAPL", "twelvedata", Period.QUARTERLY, "max")
        service.load_fundamentals("AAPL", "twelvedata", Period.ANNUAL, "max")
        assert len(adapter.calls) == 2

        service.load_fundamentals("AAPL", "twelvedata", Period.TTM, "max")
        service.load_fundamentals("AAPL", "twelvedata", Period.TTM, "max")

    assert len(adapter.calls) == 2  # TTM, loaded twice, fetched nothing


def test_ttm_notes_describe_ttm_not_the_quarterly_fetch_it_was_built_from(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    with patch("investigraph.web.service.get_source", return_value=_PeriodAdapter()):
        result = service.load_fundamentals("AAPL", "twelvedata", Period.TTM, "max")

    # "max" exceeds the declared 6y TTM depth, so a TTM limit is expected; the shallow
    # QUARTERLY (1y) / ANNUAL limits are about other fetches and must not be inherited.
    assert any("for ttm" in limit for limit in result.source_limits)
    assert not any("for quarterly" in limit for limit in result.source_limits)
    assert not any("for annual" in limit for limit in result.source_limits)


def test_ttm_still_loads_when_the_annual_fetch_fails_and_nothing_is_cached(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    adapter = _PeriodAdapter(annual_error=SourceUnavailable("out of credits"))
    with patch("investigraph.web.service.get_source", return_value=adapter):
        result = service.load_fundamentals("AAPL", "twelvedata", Period.TTM, "max")

    assert result.period == Period.TTM
    assert (
        _ttm_eps(result)[date(2026, 3, 31)] == 4.0
    )  # the quarterly rolling sum survives
