"""Fetch orchestration for the web module, composed only from published interfaces.

This slice is independent: it reaches into no other module's internals, it only
calls the same public functions the CLI does (market_of, get_source, TemplateCache,
check_request). The CLI keeps its own copy of this flow — the two do not share
private code, by design.
"""

from datetime import date

from financial_charts.cache.store import TemplateCache
from financial_charts.sources.base import SourceUnavailable
from financial_charts.sources.market import market_of
from financial_charts.sources.registry import get_source
from financial_charts.sources.validation import check_request
from financial_charts.template.models import CompanyFundamentals, Period


def load_fundamentals(
    ticker: str, source_name: str, period: Period, range_: str
) -> CompanyFundamentals:
    """Resolve a ticker to a `CompanyFundamentals`, cache-first, with capability limits merged.

    Raises the source layer's typed errors unchanged (`TickerNotFound`,
    `MissingCredentials`, `SourceUnavailable`, and `KeyError` for an unknown source).
    """
    market = market_of(ticker)
    adapter = get_source(source_name)
    cache = TemplateCache()
    today = date.today()

    fundamentals = cache.get(ticker, source_name, period, range_, today)
    if fundamentals is None:
        try:
            fundamentals = adapter.fetch(ticker, market, period, range_)
            cache.put(ticker, source_name, period, range_, today, fundamentals)
        except SourceUnavailable:
            stale = cache.latest(ticker, source_name, period, range_)
            if stale is None:
                raise
            stale.source_limits.append(
                "network/API unavailable; showing a stale cached page"
            )
            fundamentals = stale

    # Capability limits are a cheap, deterministic function of the request, so they are
    # computed fresh on every render path (cache hit, fetch, or stale fallback) rather
    # than persisted — a cache hit must not silently drop them. The raw fundamentals is
    # what gets cached (put above, before this merge).
    fundamentals.source_limits.extend(
        limit
        for limit in check_request(adapter.capability(), market, period, range_)
        if limit not in fundamentals.source_limits
    )
    return fundamentals
