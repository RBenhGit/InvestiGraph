"""EPS growth-rate calculations, ported from Eps_Evaluation's `normalize.ts`
(legacy/eps_evaluation/src/data/twelvedata/normalize.ts) to read the template's own
`eps` `MetricSeries` (Financial_Charts' `CompanyFundamentals`) instead of a raw
Twelve Data response — this is the one thing shared between the two apps.

`resolve_growth_rate_percent` is **the** growth-rate fallback chain:

    analyst_estimate_5y  ->  historical_3y  ->  historical_1y  ->  None

It must be called identically from every entry point (CLI and web alike) — the
pre-merge Eps_Evaluation codebase already let this chain drift apart once between
its own CLI and web adapters (an undocumented cap on one side, a silent default to
`0` on the other), producing fair values differing by up to ~47% for identical
data before it was caught. Never default a missing growth rate to `0` here — that
fabricates a fair value instead of surfacing `MISSING_GROWTH_RATE` to the caller.

`analyst_estimate_5y` has no source in this merge: Twelve Data's `growth_estimates`
endpoint (the original's source for it) is plan-gated (Ultra/Enterprise) and is not
called by this codebase's `sources/twelvedata/adapter.py` — see `docs/MERGE_SPEC.md`.
The parameter is kept so the chain's shape (and this function's tests) stay
byte-identical to the original and so a future analyst-estimate source can be
plugged in without touching every call site; in practice it is always `None` today,
and the chain degrades to `historical_3y -> historical_1y -> None`.
"""

from __future__ import annotations

import math

from investigraph.template.models import CompanyFundamentals, Money, Period, Point
from investigraph.template.trailing import ttm_series

# calculateTtmEpsGrowthPercent needs 8 consecutive quarters (4 for the current TTM
# window, 4 more for the year-ago window) — see that function's docstring for why a
# shorter-window approximation is deliberately never substituted.
_MIN_QUARTERS_FOR_TTM_GROWTH = 8


def calculate_cagr_percent(
    eps_latest: float | None, eps_past: float | None, years: float
) -> float | None:
    """Compound annual growth rate between two EPS points, as a percent.

    Undefined (returns `None`, never `NaN`) when the earlier EPS was zero or
    negative — a company that swung from a loss to a profit doesn't have a
    meaningful CAGR in this formula — or when raising a negative ratio to a
    fractional power produces a non-finite result (a swing from profit to loss).
    `NaN` must never escape this function: every caller in the fallback chain
    treats "not None" as "usable", so a `NaN` here would silently shadow a
    perfectly good growth rate sitting further down the chain.
    """
    if eps_latest is None or eps_past is None:
        return None
    if eps_past <= 0:
        return None
    if not years > 0:
        return None
    try:
        result = (math.pow(eps_latest / eps_past, 1 / years) - 1) * 100
    except (ValueError, OverflowError, ZeroDivisionError):
        return None
    return result if math.isfinite(result) else None


def historical_1y_growth_percent(fundamentals: CompanyFundamentals) -> float | None:
    """CAGR between the latest annual EPS point and the one 1 year before it."""
    values = _annual_eps_values(fundamentals)
    if values is None or len(values) < 2:
        return None
    return calculate_cagr_percent(values[0], values[1], 1)


def historical_3y_growth_percent(fundamentals: CompanyFundamentals) -> float | None:
    """CAGR between the latest annual EPS point and the one 3 years before it."""
    values = _annual_eps_values(fundamentals)
    if values is None or len(values) < 4:
        return None
    return calculate_cagr_percent(values[0], values[3], 3)


def resolve_growth_rate_percent(
    analyst_estimate_5y_percent: float | None,
    historical_3y_percent: float | None,
    historical_1y_percent: float | None,
) -> float | None:
    """The one growth-rate fallback chain, shared by every caller so it can never
    drift the way it once did between the CLI and web adapters (see module
    docstring). Any non-`None` value is used as-is, including `0.0` — only the
    total absence of all three sources becomes `None`, never a fabricated `0`.
    """
    if analyst_estimate_5y_percent is not None:
        return analyst_estimate_5y_percent
    if historical_3y_percent is not None:
        return historical_3y_percent
    if historical_1y_percent is not None:
        return historical_1y_percent
    return None


def calculate_ttm_eps_growth_percent(fundamentals: CompanyFundamentals) -> float | None:
    """True TTM-EPS growth: TTM ending at the latest quarter vs. TTM ending
    exactly 4 quarters earlier — distinct from `historical_1y_growth_percent`
    above, which compares calendar-year annual EPS, not rolling 12-month windows.

    Requires `fundamentals.period == Period.QUARTERLY` with at least 8
    consecutive quarterly `eps` points; returns `None` rather than approximate
    from fewer (see the TS source's comment on a live ABBV case where a
    6-months-apart comparison diverged wildly from the true 12-month figure).

    The "year ago" TTM point is chosen by date, not by a fixed list position:
    `eps_series.points` can have an interior gap (a missing quarter — both
    adapters drop a `None`/`NaN` statement cell rather than fabricate one), and
    `ttm_series` itself silently skips any 4-quarter window spanning more than
    ~330 days. A fixed "5th-from-the-end" index would then quietly pair the
    latest TTM point against one from *more* than a year back — exactly the
    mismatched-window bug this function exists to refuse.
    """
    if fundamentals.period != Period.QUARTERLY:
        return None
    eps_series = fundamentals.series.get("eps")
    if eps_series is None or not eps_series.available:
        return None
    if len(eps_series.points) < _MIN_QUARTERS_FOR_TTM_GROWTH:
        return None

    ttm = ttm_series(eps_series, Period.QUARTERLY)
    if len(ttm.points) < 2:
        return None

    ttm_points = sorted(ttm.points, key=lambda point: point.date)
    ttm_now = ttm_points[-1]
    ttm_year_ago = _find_year_ago_point(ttm_now, ttm_points[:-1])
    if ttm_year_ago is None:
        return None

    now = _as_float_value(ttm_now.value)
    year_ago = _as_float_value(ttm_year_ago.value)
    if now is None or year_ago is None or year_ago <= 0:
        return None

    result = (now / year_ago - 1) * 100
    return result if math.isfinite(result) else None


# The date gap between "TTM now" and "TTM one year ago" should span four
# quarterly steps (~364-368 days for a healthy, gap-free run of quarters). A
# comparison silently missing one quarter's TTM point (five steps) spans
# roughly ~455-460 days from the *next* candidate; 410 splits the two with
# margin on both sides — the same "give margin on both sides" reasoning
# `template/trailing.py`'s own `_MAX_QUARTER_WINDOW_DAYS` uses for a single
# 4-quarter window, applied here to the year-over-year gap between two TTM
# points instead.
_MIN_YEAR_AGO_GAP_DAYS = 330
_MAX_YEAR_AGO_GAP_DAYS = 410


def _find_year_ago_point(ttm_now: Point, earlier_points: list[Point]) -> Point | None:
    """The most recent point in `earlier_points` whose date is within one
    year (`_MIN_YEAR_AGO_GAP_DAYS`-`_MAX_YEAR_AGO_GAP_DAYS`) of `ttm_now`'s.

    `earlier_points` is ascending by date and entirely before `ttm_now`, so
    walking it back-to-front makes the gap grow monotonically — once it
    exceeds the max, no earlier candidate can possibly qualify either.
    """
    for candidate in reversed(earlier_points):
        gap_days = (ttm_now.date - candidate.date).days
        if gap_days > _MAX_YEAR_AGO_GAP_DAYS:
            return None
        if gap_days >= _MIN_YEAR_AGO_GAP_DAYS:
            return candidate
    return None


def _as_float_value(value: Money | float) -> float | None:
    raw = value.as_base_units() if isinstance(value, Money) else value
    if not isinstance(raw, (int, float)) or (
        isinstance(raw, float) and math.isnan(raw)
    ):
        return None
    return float(raw)


def _annual_eps_values(fundamentals: CompanyFundamentals) -> list[float] | None:
    """Most-recent-first list of annual EPS values (base units), or `None` when
    `fundamentals` isn't an annual-period fetch or has no usable `eps` series.
    """
    if fundamentals.period != Period.ANNUAL:
        return None
    eps_series = fundamentals.series.get("eps")
    if eps_series is None or not eps_series.available:
        return None

    # Positional, not filtered: `historical_1y`/`historical_3y` index into this by
    # "N years ago", the same positional contract the original TS used against its
    # own `annualEps` array — dropping an entry here would silently shift every
    # later index and pair the wrong two years together.
    points = sorted(eps_series.points, key=lambda point: point.date, reverse=True)
    return [
        point.value.as_base_units() if isinstance(point.value, Money) else point.value
        for point in points
    ]
