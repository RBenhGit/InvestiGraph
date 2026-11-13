"""Spot FX rate via `yfinance` (`USDILS=X`-style pair symbols).

**Not a `DataSource`** (see `sources/base.py`) — same sibling-module shape as
`sources/yahoo_consensus/`: it never produces a `CompanyFundamentals` and must not be
registered in `sources/registry.py`. Any failure (network, unknown pair, junk value)
degrades to `None`; callers decide what a missing rate means, this module never raises.

The rate is a *current* spot rate. It is right for converting a current TTM EPS into
the price currency for a fair-value comparison against today's price. It is **not**
right for converting historical points (the rate moved over the window), so nothing
here is suitable for rescaling whole series. For a time-varying comparison (the P/E
chart) use `fetch_fx_history` / `attach_fx_series`, which give a rate per date.
"""

from __future__ import annotations

import math
from datetime import date, timedelta

import yfinance as yf

from investigraph.template.models import (
    CompanyFundamentals,
    Currency,
    MetricSeries,
    Money,
    Point,
)
from investigraph.template.trailing import FX_RATE_METRIC_ID


def fetch_fx_rate(from_currency: Currency, to_currency: Currency) -> float | None:
    """Units of `to_currency` per one unit of `from_currency` (USD->ILS ~ 3.2), or
    `None` if no finite positive rate could be fetched."""
    symbol = f"{from_currency.value}{to_currency.value}=X"
    try:
        rate = yf.Ticker(symbol).fast_info["lastPrice"]
    except Exception:
        return None
    if not isinstance(rate, (int, float)) or not math.isfinite(rate) or rate <= 0:
        return None
    return float(rate)


def fetch_fx_history(
    from_currency: Currency, to_currency: Currency, start: date, end: date
) -> MetricSeries | None:
    """Daily closes of the pair over `start..end` inclusive, as a float `fx_rate` series
    (`to_currency` per one `from_currency`), or `None` if nothing usable came back."""
    symbol = f"{from_currency.value}{to_currency.value}=X"
    try:
        frame = yf.Ticker(symbol).history(
            start=start.isoformat(), end=(end + timedelta(days=1)).isoformat()
        )
        closes = frame["Close"]
        points = [
            Point(date=index.date(), value=float(close))
            for index, close in closes.items()
            if math.isfinite(close) and close > 0
        ]
    except Exception:
        return None
    if not points:
        return None
    return MetricSeries(metric_id=FX_RATE_METRIC_ID, points=points, available=True)


def attach_fx_series(fundamentals: CompanyFundamentals) -> None:
    """Add an `fx_rate` series when `eps` and `price` are denominated in different
    currencies (a TASE ticker filing in USD but quoted in ILS), so the P/E chart can
    convert EPS at each price date's rate. A no-op — and no network call — when the
    currencies match, when either series is missing, or when the fetch fails (the P/E
    chart then stays "no data" rather than mixing currencies)."""
    eps = fundamentals.series.get("eps")
    price = fundamentals.series.get("price")
    if eps is None or price is None or not eps.available or not price.available:
        return
    eps_currencies = {
        p.value.currency for p in eps.points if isinstance(p.value, Money)
    }
    price_currencies = {
        p.value.currency for p in price.points if isinstance(p.value, Money)
    }
    if len(eps_currencies) != 1 or len(price_currencies) != 1:
        return
    (eps_currency,), (price_currency,) = eps_currencies, price_currencies
    if eps_currency == price_currency:
        return
    dates = [p.date for p in price.points]
    history = fetch_fx_history(eps_currency, price_currency, min(dates), max(dates))
    if history is not None:
        fundamentals.series[FX_RATE_METRIC_ID] = history
