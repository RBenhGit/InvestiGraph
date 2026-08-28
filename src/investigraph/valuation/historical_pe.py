"""Historical median trailing P/E, ported from Eps_Evaluation's `historicalPe.ts`
(legacy/eps_evaluation/src/data/twelvedata/historicalPe.ts) to read the template's
own annual `eps` and daily `price` series instead of raw Twelve Data responses.

Median, not mean: with as few as 1-5 points per window (one per fiscal year), one
outlier year (a temporarily depressed EPS, a price spike) would dominate a mean;
the median is far less sensitive to that, at the cost of no longer being a literal
"average" despite the field names (`avg_1y` etc., kept for continuity with the
original's `HistoricalPeAverages` shape). A window needs at least half its points
(rounded up) to be valid at all — one bad year doesn't null out the whole window,
but a window that's mostly bad years isn't meaningful either.

This deliberately does **not** reuse `template/trailing.py`'s `PE_RATIO_TTM` (a
full *daily* trailing-P/E series, one point per price date): that's a different
statistic with different statistical properties (median over hundreds of daily
points within a window vs. median over up to N *annual* points, one per fiscal
year) and would silently change what "median 3y P/E" means and produce different
numbers than the original tool. This module intentionally stays one point per
fiscal year, using the template's own annual `eps` series (so callers must fetch
`Period.ANNUAL` — the same requirement `valuation/growth.py`'s historical CAGR
functions already have) paired against the daily `price` series's nearest
preceding close, more precise than the original's monthly-close granularity but
the same "one point per fiscal year" methodology.
"""

from __future__ import annotations

import bisect
from dataclasses import dataclass

from investigraph.template.models import CompanyFundamentals, Money, Period


@dataclass(frozen=True)
class HistoricalPeAverages:
    avg_1y: float | None
    avg_3y: float | None
    avg_5y: float | None


def compute_historical_pe_averages(
    fundamentals: CompanyFundamentals,
) -> HistoricalPeAverages:
    """`avg_1y`/`avg_3y`/`avg_5y`: the median trailing P/E over the 1/3/5 most
    recent fiscal years, each year's P/E computed from that year's diluted EPS
    and the nearest preceding daily close. `None` for a window with too few
    valid (positive-EPS, price-available) years — see `_median_window`.
    """
    points = _annual_pe_points(fundamentals)
    return HistoricalPeAverages(
        avg_1y=_median_window(points, 1),
        avg_3y=_median_window(points, 3),
        avg_5y=_median_window(points, 5),
    )


def _annual_pe_points(fundamentals: CompanyFundamentals) -> list[float | None]:
    """One P/E point per fiscal year, most-recent-first; `None` for a year with
    non-positive EPS or no preceding price point available at all."""
    if fundamentals.period != Period.ANNUAL:
        return []
    eps_series = fundamentals.series.get("eps")
    price_series = fundamentals.series.get("price")
    if (
        eps_series is None
        or not eps_series.available
        or price_series is None
        or not price_series.available
    ):
        return []

    price_points = sorted(price_series.points, key=lambda p: p.date)
    price_dates = [p.date for p in price_points]

    annual_points = sorted(eps_series.points, key=lambda p: p.date, reverse=True)
    results: list[float | None] = []
    for point in annual_points:
        eps = (
            point.value.as_base_units()
            if isinstance(point.value, Money)
            else point.value
        )
        if eps <= 0:
            results.append(None)
            continue
        idx = bisect.bisect_right(price_dates, point.date) - 1
        if idx < 0:
            results.append(None)
            continue
        close = price_points[idx].value
        close_value = close.as_base_units() if isinstance(close, Money) else close
        results.append(close_value / eps)
    return results


def _median_window(points: list[float | None], window_size: int) -> float | None:
    window = points[:window_size]
    valid = sorted(p for p in window if p is not None)
    if len(valid) == 0 or len(valid) < -(-window_size // 2):  # ceil(window_size / 2)
        return None
    mid = len(valid) // 2
    if len(valid) % 2 == 1:
        return valid[mid]
    return (valid[mid - 1] + valid[mid]) / 2
