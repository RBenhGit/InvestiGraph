from datetime import date, datetime, timedelta, timezone

from investigraph.sources.yahoo_consensus.cache import AnalystConsensusCache
from investigraph.sources.yahoo_consensus.models import (
    AnalystConsensus,
    AnalystPriceTarget,
)


def _consensus(as_of: datetime | None = None) -> AnalystConsensus:
    return AnalystConsensus(
        ticker="AAPL",
        next_year_eps_growth_percent=8.09,
        price_target=AnalystPriceTarget(
            mean=324.45, high=400.0, low=215.0, number_of_analysts=39
        ),
        recommendation_key="buy",
        beta=1.086,
        price_to_sales=10.02,
        rule_of_40=None,
        trailing_eps=8.71,
        most_recent_quarter_end_date=date(2026, 6, 27),
        as_of=as_of or datetime.now(timezone.utc),
    )


def test_cache_miss_returns_none(tmp_path):
    cache = AnalystConsensusCache(cache_dir=tmp_path)
    assert cache.get("AAPL", date(2026, 8, 28)) is None


def test_put_then_get_round_trips(tmp_path):
    cache = AnalystConsensusCache(cache_dir=tmp_path)
    consensus = _consensus()
    as_of = date(2026, 8, 28)

    cache.put("AAPL", as_of, consensus)
    loaded = cache.get("AAPL", as_of)

    assert loaded == consensus


def test_key_distinguishes_ticker_and_date(tmp_path):
    cache = AnalystConsensusCache(cache_dir=tmp_path)
    consensus = _consensus()
    as_of = date(2026, 8, 28)
    cache.put("AAPL", as_of, consensus)

    assert cache.get("MSFT", as_of) is None
    assert cache.get("AAPL", date(2026, 8, 27)) is None


def test_get_returns_none_for_an_entry_older_than_the_ttl(tmp_path):
    cache = AnalystConsensusCache(cache_dir=tmp_path, ttl=timedelta(hours=24))
    stale = _consensus(as_of=datetime.now(timezone.utc) - timedelta(hours=25))
    as_of = date(2026, 8, 28)
    cache.put("AAPL", as_of, stale)

    assert cache.get("AAPL", as_of) is None


def test_get_returns_the_entry_when_within_the_ttl(tmp_path):
    cache = AnalystConsensusCache(cache_dir=tmp_path, ttl=timedelta(hours=24))
    fresh = _consensus(as_of=datetime.now(timezone.utc) - timedelta(hours=1))
    as_of = date(2026, 8, 28)
    cache.put("AAPL", as_of, fresh)

    assert cache.get("AAPL", as_of) == fresh


def test_get_returns_none_for_a_corrupt_cache_file_instead_of_crashing(tmp_path):
    cache = AnalystConsensusCache(cache_dir=tmp_path)
    as_of = date(2026, 8, 28)
    path = cache._path("AAPL", as_of)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not valid json{{{")

    assert cache.get("AAPL", as_of) is None


def test_put_leaves_no_temp_file_behind(tmp_path):
    cache = AnalystConsensusCache(cache_dir=tmp_path)
    cache.put("AAPL", date(2026, 8, 28), _consensus())

    assert list(tmp_path.glob("*.tmp-*")) == []
