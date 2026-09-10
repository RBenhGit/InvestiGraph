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


def fit_linear(dates: list[date], values: list[float]) -> FitResult | None:
    """Ordinary least-squares line through `values` over `dates`.

    Returns `None` only when a fit is degenerate (fewer than 2 points, or
    every date identical) — otherwise always succeeds, since a line is
    defined for any real y-values, including zero or negative ones.
    """
    if len(dates) < 2:
        return None
    x = _years_since_first(dates)
    if x[0] == x[-1] and len(set(x)) == 1:
        return None

    slope, intercept = _polyfit_degree1(x, values)
    fitted = [slope * xi + intercept for xi in x]
    return FitResult(fitted_values=fitted, rate=slope)


def fit_exponential(dates: list[date], values: list[float]) -> FitResult | None:
    """Least-squares exponential curve (`y = a * exp(b * years)`) through
    `values` over `dates`, fit by ordinary least squares on `log(values)`.

    Returns `None` when a fit is degenerate (same conditions as
    `fit_linear`) or when any value is non-positive — a real logarithm
    doesn't exist for a zero or negative value (e.g. a loss-making year's
    net income), so this degrades to "no exponential fit" rather than
    fabricating one from a partial series, the same "unavailable, not
    wrong" posture `template/derived.py`'s `ratio()` guards take.
    """
    if len(dates) < 2:
        return None
    if any(v <= 0 for v in values):
        return None
    x = _years_since_first(dates)
    if x[0] == x[-1] and len(set(x)) == 1:
        return None

    log_values = [math.log(v) for v in values]
    slope, intercept = _polyfit_degree1(x, log_values)
    fitted = [math.exp(slope * xi + intercept) for xi in x]
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
