"""Trailing-twelve-month (TTM) series, and price-driven ratios computed from them.

A sibling of `derived.py`: where `derived.resolve` joins same-cadence inputs on
their exact common dates, the metrics here pair a fast-moving daily driver
(typically `price`) against slower statement-cadence inputs, sampled *as of*
each driver date — never a future one. Flow-metric inputs (EPS, net income,
dividends paid) are first turned into a rolling trailing-twelve-month view via
`ttm_series`; point-in-time inputs (shares outstanding, total equity) are
joined as-is.
"""

from __future__ import annotations

import bisect
import math
from dataclasses import dataclass
from datetime import date
from functools import reduce
from operator import add
from typing import Callable

from investigraph.template.derived import DerivedMetric, ratio, resolve
from investigraph.template.models import (
    CompanyFundamentals,
    Money,
    MetricSeries,
    Period,
    Point,
    Unit,
)

# Four healthy consecutive quarter-end dates span ~273-289 days (three ~91-92
# day gaps, a little wider for 53-week fiscal years / shifted quarter ends).
# A window silently missing one quarter spans roughly double that. 330 splits
# the two with margin on both sides.
_MAX_QUARTER_WINDOW_DAYS = 330


def ttm_series(series: MetricSeries, period: Period) -> MetricSeries:
    """Trailing-twelve-month view of a flow metric (EPS, net income, dividends paid).

    Under `Period.ANNUAL` each point already represents a trailing year as of
    its fiscal date, so this is the identity. Under `Period.QUARTERLY`, sums
    each rolling window of 4 consecutive quarters — a window whose span
    indicates a missing quarter is skipped rather than silently understating
    the total, the same "degrade one point, not the whole series" contract as
    `derived.resolve`.
    """
    if period != Period.QUARTERLY:
        return series
    if not series.available:
        return MetricSeries(metric_id=series.metric_id, available=False)

    points = sorted(series.points, key=lambda p: p.date)
    ttm_points: list[Point] = []
    for i in range(3, len(points)):
        window = points[i - 3 : i + 1]
        if (window[-1].date - window[0].date).days > _MAX_QUARTER_WINDOW_DAYS:
            continue
        try:
            total = reduce(add, (p.value for p in window))
        except (TypeError, ValueError):
            continue
        ttm_points.append(Point(date=window[-1].date, value=total))

    return MetricSeries(
        metric_id=series.metric_id, points=ttm_points, available=bool(ttm_points)
    )


# The 20-metric catalog both `sources/yfinance/adapter.py` and
# `sources/twelvedata/adapter.py` populate. Flow (income/cash-flow-statement) metrics
# sum correctly over a trailing 4-quarter window; everything else in `CompanyFundamentals.series`
# that isn't listed here (balance-sheet snapshots, `price`, `gross_margin`) is treated as
# point-in-time and passed through unchanged by `derive_ttm_fundamentals` — the safe default
# for any metric this table doesn't yet know about, since summing a point-in-time value would
# be the wrong failure mode (a wrong number) rather than the right one (a missing one).
_FLOW_METRIC_IDS = frozenset(
    {
        "revenue",
        "net_income",
        "eps",
        "free_cash_flow",
        "ebitda",
        "research_and_development",
        "selling_general_administrative",
        "dividends_paid",
        "ebit",
    }
)

_NET_MARGIN = DerivedMetric(
    metric_id="net_margin",
    title="Net Margin",
    inputs=("net_income", "revenue"),
    compute=ratio,
)

_GROSS_MARGIN_TTM_NOTE = (
    "gross_margin under the derived TTM period is each quarter's own margin, not a true "
    "trailing-twelve-month figure (its numerator isn't tracked as its own series)"
)


def derive_ttm_fundamentals(quarterly: CompanyFundamentals) -> CompanyFundamentals:
    """Derive a `Period.TTM` `CompanyFundamentals` from a `Period.QUARTERLY` one.

    Both registered sources' `capability.py` now declare `Period.TTM`, but neither adapter
    fetches it natively — Twelve Data has no TTM endpoint, and while yfinance does expose
    one for income statement / cash flow, using it there and deriving here for Twelve Data
    would make TTM behave differently depending on which source is selected. Both adapters
    fetch `Period.QUARTERLY` and this function derives TTM from it uniformly, by summing the
    trailing four quarters of each flow metric via `ttm_series`. Point-in-time
    (balance-sheet) metrics and `price` pass through unchanged (their *whole* quarterly
    series, not just the latest point), since each of their points already represents a
    snapshot as of its own date. `net_margin` is recomputed from the newly-TTM'd
    `net_income`/`revenue` (both independently available as flow series, so this is the
    correct TTM figure, not an approximation) via the same `derived.resolve` machinery
    `template/derived.py` already uses for other cross-metric ratios. `gross_margin` is the
    one exception: its numerator (`Gross Profit`) isn't stored as its own series in either
    adapter, so it can't be correctly recomputed here — its whole quarterly series passes
    through instead (each point still that quarter's own margin, not a trailing one), with a
    `source_limits` note disclosing the approximation.
    """
    if quarterly.period != Period.QUARTERLY:
        raise ValueError(
            "derive_ttm_fundamentals requires Period.QUARTERLY input, got "
            f"{quarterly.period.value}"
        )

    new_series: dict[str, MetricSeries] = {}
    for metric_id, series in quarterly.series.items():
        if metric_id in _FLOW_METRIC_IDS:
            new_series[metric_id] = ttm_series(series, Period.QUARTERLY)
        elif metric_id != "net_margin":
            new_series[metric_id] = series

    if "net_margin" in quarterly.series:
        # A temporary TTM-period view carrying the already-TTM'd net_income/revenue,
        # so `resolve` joins on their new (still-matching) dates rather than the raw
        # quarterly ones.
        interim = quarterly.model_copy(
            update={"period": Period.TTM, "series": new_series}
        )
        new_series["net_margin"] = resolve(interim, _NET_MARGIN)

    source_limits = list(quarterly.source_limits)
    gross_margin = quarterly.series.get("gross_margin")
    if gross_margin is not None and gross_margin.available:
        source_limits.append(_GROSS_MARGIN_TTM_NOTE)

    return quarterly.model_copy(
        update={
            "period": Period.TTM,
            "series": new_series,
            "source_limits": source_limits,
        }
    )


@dataclass(frozen=True)
class TrailingInput:
    """One input to a `TrailingMetric`.

    `ttm=True` marks a flow metric that must pass through `ttm_series` before
    joining; point-in-time metrics (shares outstanding, total equity) are
    joined as-is.
    """

    metric_id: str
    ttm: bool = False


@dataclass(frozen=True)
class TrailingMetric:
    """A metric computed by joining a lead series against other inputs as of
    each lead date — never a future one.

    `driver`, when set, names a metric (typically `price`) whose own dates
    become the output's dates, with every input in `inputs` sampled as of
    each driver date. When `driver` is `None`, the first entry in `inputs`
    plays that role instead (its own dates become the output's dates) and the
    remaining inputs are as-of joined against it — for a metric with no
    natural daily driver (e.g. ROE), this keeps the output at statement
    cadence instead of manufacturing a false daily density.

    `compute` is called as `compute(driver_value, *asof_input_values)` (or
    `compute(first_input_value, *asof_rest_values)` when `driver` is `None`),
    in the declared order of `inputs`.
    """

    metric_id: str
    title: str
    driver: str | None
    inputs: tuple[TrailingInput, ...]
    compute: Callable[..., Money | float]


def _prepare_input(
    fundamentals: CompanyFundamentals, input_spec: TrailingInput
) -> MetricSeries | None:
    raw = fundamentals.series.get(input_spec.metric_id)
    if raw is None or not raw.available:
        return None
    series = ttm_series(raw, fundamentals.period) if input_spec.ttm else raw
    return series if series.available else None


def _asof_table(series: MetricSeries) -> tuple[list[date], dict[date, Money | float]]:
    ordered = sorted(series.points, key=lambda p: p.date)
    dates = [p.date for p in ordered]
    values = {p.date: p.value for p in ordered}
    return dates, values


def resolve_trailing(
    fundamentals: CompanyFundamentals, metric: TrailingMetric
) -> MetricSeries:
    """Compute `metric`'s series against `fundamentals`.

    Unavailable iff the driver (when declared) or any input is missing or
    unavailable — the same propagation contract as `derived.resolve`. A point
    whose as-of value isn't yet known (a driver date before the first input
    date — no lookahead) or whose `compute` raises is skipped, not a crash.
    """
    if metric.driver is not None:
        driver_series = fundamentals.series.get(metric.driver)
        if driver_series is None or not driver_series.available:
            return MetricSeries(metric_id=metric.metric_id, available=False)
        lead_points = sorted(driver_series.points, key=lambda p: p.date)
        asof_inputs = metric.inputs
    else:
        if not metric.inputs:
            return MetricSeries(metric_id=metric.metric_id, available=False)
        lead_input, *asof_inputs = metric.inputs
        lead_series = _prepare_input(fundamentals, lead_input)
        if lead_series is None:
            return MetricSeries(metric_id=metric.metric_id, available=False)
        lead_points = sorted(lead_series.points, key=lambda p: p.date)

    asof_tables = []
    for input_spec in asof_inputs:
        series = _prepare_input(fundamentals, input_spec)
        if series is None:
            return MetricSeries(metric_id=metric.metric_id, available=False)
        asof_tables.append(_asof_table(series))

    points: list[Point] = []
    for lead in lead_points:
        asof_values: list[Money | float] | None = []
        for dates, values in asof_tables:
            idx = bisect.bisect_right(dates, lead.date) - 1
            if idx < 0:
                asof_values = None
                break
            asof_values.append(values[dates[idx]])
        if asof_values is None:
            # No input is known yet as of this date — the series simply
            # hasn't started, not a bad value to break a line at.
            continue
        try:
            value = metric.compute(lead.value, *asof_values)
        except (ZeroDivisionError, ValueError, AttributeError, TypeError):
            # A single date where the metric is undefined (e.g. non-positive
            # TTM EPS, a zero denominator) must break the plotted line here,
            # not silently vanish — omitting the point instead would let the
            # renderer draw a straight line connecting the surrounding valid
            # points *through* the gap, fabricating values for a date no
            # number was actually computed for. NaN is the same convention
            # `_price`'s SMA warm-up period already relies on to open a gap
            # in both the matplotlib and Plotly renderers.
            points.append(Point(date=lead.date, value=float("nan")))
            continue
        points.append(Point(date=lead.date, value=value))

    if not any(_is_real(p.value) for p in points):
        # Every date failed (or none were reached at all) — an all-NaN
        # series isn't "available data with gaps", it's no data.
        points = []

    return MetricSeries(
        metric_id=metric.metric_id, points=points, available=bool(points)
    )


def _is_real(value: Money | float) -> bool:
    raw = value.value if isinstance(value, Money) else value
    return not (isinstance(raw, float) and math.isnan(raw))


def _pe(price: Money, eps_ttm: Money) -> float:
    if eps_ttm.as_base_units() <= 0:
        # Trailing P/E is conventionally left blank for a loss-making
        # trailing year rather than plotted as a meaningless negative number.
        raise ValueError("non-positive TTM EPS")
    return ratio(price, eps_ttm)


PE_RATIO_TTM = TrailingMetric(
    metric_id="pe_ratio_ttm",
    title="P/E (TTM)",
    driver="price",
    inputs=(TrailingInput("eps", ttm=True),),
    compute=_pe,
)


def _market_cap(price: Money, shares: float) -> Money:
    return Money(
        value=price.as_base_units() * shares, currency=price.currency, scale=Unit.ONES
    )


MARKET_CAP = TrailingMetric(
    metric_id="market_cap_daily",
    title="Market Cap",
    driver="price",
    inputs=(TrailingInput("shares_outstanding"),),
    compute=_market_cap,
)


def _dividend_yield(price: Money, dividends_ttm: Money, shares: float) -> float:
    # A dual-listed company can report financials in a different currency
    # than the one its shares trade in (see Money.require_same_currency).
    price.require_same_currency(dividends_ttm)
    dividend_per_share = dividends_ttm.as_base_units() / shares
    return dividend_per_share / price.as_base_units()


DIVIDEND_YIELD_TTM = TrailingMetric(
    metric_id="dividend_yield_ttm",
    title="Dividend Yield (TTM)",
    driver="price",
    inputs=(
        TrailingInput("dividends_paid", ttm=True),
        TrailingInput("shares_outstanding"),
    ),
    compute=_dividend_yield,
)


ROE_TTM = TrailingMetric(
    metric_id="roe_ttm",
    title="ROE (TTM)",
    driver=None,
    inputs=(
        TrailingInput("net_income", ttm=True),
        TrailingInput("total_equity"),
    ),
    compute=ratio,
)
