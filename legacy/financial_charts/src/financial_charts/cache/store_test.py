from datetime import date

from financial_charts.cache.store import TemplateCache
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


def _fundamentals() -> CompanyFundamentals:
    return CompanyFundamentals(
        ticker="AAPL",
        market=Market.US,
        currency=Currency.USD,
        period=Period.ANNUAL,
        range="5y",
        series={
            "revenue": MetricSeries(
                metric_id="revenue",
                points=[
                    Point(
                        date=date(2025, 9, 30),
                        value=Money(
                            value=416_161_000_000,
                            currency=Currency.USD,
                            scale=Unit.ONES,
                        ),
                    )
                ],
                available=True,
            )
        },
        source_limits=["eps: no data available for this ticker"],
    )


def test_cache_miss_returns_none(tmp_path):
    cache = TemplateCache(cache_dir=tmp_path)
    assert cache.get("AAPL", "yfinance", Period.ANNUAL, "5y", date(2026, 7, 19)) is None


def test_put_then_get_round_trips(tmp_path):
    cache = TemplateCache(cache_dir=tmp_path)
    fundamentals = _fundamentals()
    as_of = date(2026, 7, 19)

    cache.put("AAPL", "yfinance", Period.ANNUAL, "5y", as_of, fundamentals)
    loaded = cache.get("AAPL", "yfinance", Period.ANNUAL, "5y", as_of)

    assert loaded == fundamentals


def test_key_distinguishes_source_period_range_and_date(tmp_path):
    cache = TemplateCache(cache_dir=tmp_path)
    fundamentals = _fundamentals()
    as_of = date(2026, 7, 19)
    cache.put("AAPL", "yfinance", Period.ANNUAL, "5y", as_of, fundamentals)

    assert cache.get("AAPL", "twelvedata", Period.ANNUAL, "5y", as_of) is None
    assert cache.get("AAPL", "yfinance", Period.QUARTERLY, "5y", as_of) is None
    assert cache.get("AAPL", "yfinance", Period.ANNUAL, "10y", as_of) is None
    assert cache.get("AAPL", "yfinance", Period.ANNUAL, "5y", date(2026, 7, 20)) is None


def test_latest_returns_none_when_nothing_cached(tmp_path):
    cache = TemplateCache(cache_dir=tmp_path)
    assert cache.latest("AAPL", "yfinance", Period.ANNUAL, "5y") is None


def test_latest_returns_most_recent_dated_entry(tmp_path):
    cache = TemplateCache(cache_dir=tmp_path)
    fundamentals = _fundamentals()

    cache.put("AAPL", "yfinance", Period.ANNUAL, "5y", date(2026, 7, 1), fundamentals)
    cache.put("AAPL", "yfinance", Period.ANNUAL, "5y", date(2026, 7, 19), fundamentals)

    latest = cache.latest("AAPL", "yfinance", Period.ANNUAL, "5y")
    assert latest == fundamentals


def test_get_returns_none_for_a_corrupt_cache_file_instead_of_crashing(tmp_path):
    cache = TemplateCache(cache_dir=tmp_path)
    as_of = date(2026, 7, 19)
    path = cache._path("AAPL", "yfinance", Period.ANNUAL, "5y", as_of)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not valid json{{{")

    assert cache.get("AAPL", "yfinance", Period.ANNUAL, "5y", as_of) is None


def test_latest_skips_a_corrupt_entry_and_falls_back_to_an_older_valid_one(tmp_path):
    cache = TemplateCache(cache_dir=tmp_path)
    fundamentals = _fundamentals()
    cache.put("AAPL", "yfinance", Period.ANNUAL, "5y", date(2026, 7, 1), fundamentals)

    corrupt_path = cache._path(
        "AAPL", "yfinance", Period.ANNUAL, "5y", date(2026, 7, 19)
    )
    corrupt_path.write_text("not valid json{{{")

    assert cache.latest("AAPL", "yfinance", Period.ANNUAL, "5y") == fundamentals


def test_put_leaves_no_temp_file_behind(tmp_path):
    cache = TemplateCache(cache_dir=tmp_path)
    cache.put(
        "AAPL", "yfinance", Period.ANNUAL, "5y", date(2026, 7, 19), _fundamentals()
    )

    assert list(tmp_path.glob("*.tmp-*")) == []
