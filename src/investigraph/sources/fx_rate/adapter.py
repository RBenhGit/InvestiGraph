"""Spot FX rate via `yfinance` (`USDILS=X`-style pair symbols).

**Not a `DataSource`** (see `sources/base.py`) — same sibling-module shape as
`sources/yahoo_consensus/`: it never produces a `CompanyFundamentals` and must not be
registered in `sources/registry.py`. Any failure (network, unknown pair, junk value)
degrades to `None`; callers decide what a missing rate means, this module never raises.

The rate is a *current* spot rate. It is right for converting a current TTM EPS into
the price currency for a fair-value comparison against today's price. It is **not**
right for converting historical points (the rate moved over the window), so nothing
here is suitable for rescaling whole series.
"""

from __future__ import annotations

import math

import yfinance as yf

from investigraph.template.models import Currency


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
