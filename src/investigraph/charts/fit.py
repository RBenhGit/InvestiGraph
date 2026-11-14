"""Linear/exponential trend-fit overlays for growth-style charts (Revenue, Net
Income, EPS, FCF — see `docs/UX_NOTES.md`).

Both fits are plotted against the same x-axis: days since the series' first
point, in fractional years. This gives the linear fit's slope units of
"per year" directly, and lets both fits use one shared x-axis-building helper
regardless of which chart's dates they're computed from.

`fit_linear`/`fit_exponential` are pure numeric functions independent of
`Money`/matplotlib/Plotly — the caller (a `charts/builtins/*.py` chart or a
`web/chart_data.py` shaper) is responsible for unwrapping `Money.as_base_units()`
into a plain `list[float]` first, the same division of labor `charts/base.py`'s
other render helpers already follow.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class FitResult:
    """A fitted curve, resampled at the input series' own dates, plus the
    growth rate that fit implies.

    `rate` is the linear fit's slope in value-units per year for a
    `fit_linear` result, or the exponential fit's annualized growth rate
    (e.g. 0.124 for 12.4%/yr) for a `fit_exponential` result — the caller
    decides how to format/label each.
    """

    fitted_values: list[float]
    rate: float


def _years_since_first(dates: list[date]) -> list[float]:
    first = dates[0]
    return [(d - first).days / 365.25 for d in dates]


def _real_points(
    dates: list[date], values: list[float]
) -> tuple[list[date], list[float]]:
    """Drop any point whose value isn't finite.

    A TTM series (EPS, FCF — see `template/trailing.py`'s `ttm_series`) marks
    a missing-quarter gap with a NaN point rather than omitting it, so the
    line still visibly breaks there instead of interpolating straight
    through. A least-squares fit has no such per-point degrade: one NaN
    silently poisons the entire fit (`math.log(nan)` is `nan`, not an
    exception, so it slips straight past a `v <= 0` guard). Fitting only the
    real points — the same "degrade one point, not the whole series"
    contract `template/derived.py` and `template/trailing.py` use — keeps a
    single gap from erasing every fitted value instead of just its own.
    """
    real = [(d, v) for d, v in zip(dates, values) if math.isfinite(v)]
    if not real:
        return [], []
    real_dates, real_values = zip(*real)
    return list(real_dates), list(real_values)


def fit_linear(dates: list[date], values: list[float]) -> FitResult | None:
    """Ordinary least-squares line through `values` over `dates`, resampled
    back onto every input date (including ones dropped as non-finite gaps)
    so the result still aligns point-for-point with the original series.

    Returns `None` when fewer than 2 real (finite) points remain, or every
    real date is identical — otherwise always succeeds, since a line is
    defined for any real y-values, including zero or negative ones.
    """
    real_dates, real_values = _real_points(dates, values)
    if len(real_dates) < 2:
        return None
    real_x = _years_since_first(real_dates)
    if len(set(real_x)) == 1:
        return None

    slope, intercept = _polyfit_degree1(real_x, real_values)
    all_x = _years_since_first(dates)
    # Fit against real_dates' own years-since-*their*-first-date, but resample
    # against every input date's offset from the *series'* first date, so a
    # fit computed on a series missing its very first point still lines up.
    offset = (real_dates[0] - dates[0]).days / 365.25
    fitted = [slope * (xi - offset) + intercept for xi in all_x]
    return FitResult(fitted_values=fitted, rate=slope)


def fit_exponential(dates: list[date], values: list[float]) -> FitResult | None:
    """Least-squares exponential curve (`y = a * exp(b * years)`) through
    `values` over `dates`, fit by ordinary least squares on `log(values)`
    and resampled back onto every input date — see `fit_linear`.

    Returns `None` when fewer than 2 real (finite) points remain, every real
    date is identical, or any real value is non-positive — a real logarithm
    doesn't exist for a zero or negative value (e.g. a loss-making year's
    net income), so this degrades to "no exponential fit" rather than
    fabricating one from a partial series, the same "unavailable, not
    wrong" posture `template/derived.py`'s `ratio()` guards take.
    """
    real_dates, real_values = _real_points(dates, values)
    if len(real_dates) < 2:
        return None
    if any(v <= 0 for v in real_values):
        return None
    real_x = _years_since_first(real_dates)
    if len(set(real_x)) == 1:
        return None

    log_values = [math.log(v) for v in real_values]
    slope, intercept = _polyfit_degree1(real_x, log_values)
    all_x = _years_since_first(dates)
    offset = (real_dates[0] - dates[0]).days / 365.25
    fitted = [math.exp(slope * (xi - offset) + intercept) for xi in all_x]
    # exp(slope) is the per-year growth multiplier; CAGR is that minus 1
    # (e.g. a multiplier of 1.124 is a 12.4%/yr growth rate).
    cagr = math.exp(slope) - 1
    return FitResult(fitted_values=fitted, rate=cagr)


def _polyfit_degree1(x: list[float], y: list[float]) -> tuple[float, float]:
    """Ordinary least-squares slope/intercept for `y = slope * x + intercept`.

    A small dependency-free implementation (the normal equations for a
    degree-1 fit) rather than pulling in numpy/pandas for two sums — this
    module has no other numeric dependency today.
    """
    n = len(x)
    mean_x = sum(x) / n
    mean_y = sum(y) / n
    numerator = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
    denominator = sum((xi - mean_x) ** 2 for xi in x)
    if denominator == 0:
        raise ValueError("degenerate fit: every x value is identical")
    slope = numerator / denominator
    intercept = mean_y - slope * mean_x
    return slope, intercept
