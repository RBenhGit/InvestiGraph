"""Fetch orchestration for the web module, composed only from published interfaces.

This slice is independent: it reaches into no other module's internals, it only
calls the same public functions the CLI does (market_of, get_source, TemplateCache,
check_request). The CLI keeps its own copy of this flow — the two do not share
private code, by design.
"""

from datetime import date

from investigraph.cache.store import TemplateCache
from investigraph.charts.base import Chart
from investigraph.sources.base import SourceUnavailable
from investigraph.sources.fx_rate.adapter import attach_fx_series
from investigraph.sources.market import market_of
from investigraph.sources.registry import get_source
from investigraph.sources.validation import check_request
from investigraph.template.models import CompanyFundamentals, Period


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
    # Derived per render rather than cached (like the limits above), so a cache entry
    # written before this existed still gets it. A no-op unless EPS/price currencies differ.
    attach_fx_series(fundamentals)
    return fundamentals


def load_fundamentals_for_charts(
    ticker: str, source_name: str, charts: list[Chart]
) -> dict[tuple[Period, str], CompanyFundamentals]:
    """Fetch one `CompanyFundamentals` per distinct `(period, range)` pair `charts`
    actually need, not one per chart.

    Each chart now declares its own cadence/window (see `Chart.period`/`Chart.range`
    in `charts/base.py`) instead of the whole page sharing one global period+range.
    Most charts in a set agree on a handful of pairs (e.g. quarterly/max for the
    margin-style ratios, annual/max for the income-statement totals, annual/10y for
    the price-driven charts) — grouping means those charts share one fetch/cache
    entry via `load_fundamentals` instead of issuing a redundant call each.

    Raises the same typed errors as `load_fundamentals`, on the first pair that
    fails — a page load either fully succeeds or reports one error, same as today.
    """
    pairs = sorted({(chart.period, chart.range) for chart in charts})
    return {
        (period, range_): load_fundamentals(ticker, source_name, period, range_)
        for period, range_ in pairs
    }
