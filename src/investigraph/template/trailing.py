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
from dataclasses import dataclass
from datetime import date
from functools import reduce
from operator import add
from typing import Callable

from investigraph.template.derived import DerivedMetric, _is_real, ratio, resolve
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


def _nan_like(value: Money | float) -> Money | float:
    """A NaN gap marker in the same shape as `value` — `Money`-tagged with its
    currency/scale if `value` is `Money`, a bare float otherwise.

    Flow-metric series are `Money`-valued; a bare `float("nan")` mixed into
    one passes `MetricSeries`'s validation (which only checks consistency
    *among* the `Money` points) and then crashes every renderer downstream,
    which expects `.value` to be `Money` uniformly.
    """
    if isinstance(value, Money):
        return Money(value=float("nan"), currency=value.currency, scale=value.scale)
    return float("nan")


def ttm_series(
    series: MetricSeries, period: Period, *, mark_gaps: bool = False
) -> MetricSeries:
    """Trailing-twelve-month view of a flow metric (EPS, net income, dividends paid).

    Under `Period.ANNUAL` each point already represents a trailing year as of
    its fiscal date, so this is the identity. Under `Period.QUARTERLY`, sums
    each rolling window of 4 consecutive quarters.

    By default (`mark_gaps=False`) a window whose span indicates a missing
    quarter is skipped rather than silently understating the total — the
    contract `valuation/growth.py` and `valuation/resolve_eps.py` rely on to
    find "the nearest real point a year back" and "the latest real TTM point"
    by date, which a NaN-valued point would corrupt. Chart-rendering callers
    (`derive_ttm_fundamentals`) instead want a plotted line to visibly break at
    a gap rather than silently connect across it — the same "degrade one
    point, not the whole series" contract as `derived.resolve` — so they pass
    `mark_gaps=True` to get a NaN-valued point at the gap date instead of an
    omitted one. Flow metrics are `Money`-valued, so the marker is a
    `Money(value=float("nan"), ...)` tagged with the window's own
    currency/scale (via `_nan_like`), not a bare float — a bare float mixed
    into an otherwise-`Money` series passes `MetricSeries`'s validation
    (which only checks consistency *among* the `Money` points) and then
    crashes every renderer downstream, which expects `.value` to be `Money`
    uniformly.
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
            if mark_gaps:
                ttm_points.append(
                    Point(date=window[-1].date, value=_nan_like(window[0].value))
                )
            continue
        try:
            total = reduce(add, (p.value for p in window))
        except (TypeError, ValueError):
            if mark_gaps:
                ttm_points.append(
                    Point(date=window[-1].date, value=_nan_like(window[0].value))
                )
            continue
        ttm_points.append(Point(date=window[-1].date, value=total))

    if mark_gaps and not any(_is_real(p.value) for p in ttm_points):
        ttm_points = []

    return MetricSeries(
        metric_id=series.metric_id, points=ttm_points, available=bool(ttm_points)
    )


# A fiscal quarter end falls roughly 91 days after the previous one; anything outside this
# band between consecutive points is not "consecutive quarters" and must not be solved for.
_QUARTER_SPACING_DAYS = (60, 130)
# How close a quarterly point must be to a fiscal year end to count as that year's Q4.
_SAME_PERIOD_DAYS = 15


def fill_missing_fourth_quarters(
    quarterly: MetricSeries, annual: MetricSeries
) -> tuple[MetricSeries, list[date]]:
    """Add a quarter the source omitted, as the fiscal-year total minus the other three.

    Some sources report a flow metric for Q1-Q3 and the full year but no standalone Q4
    (observed for EPS: both sources omit QLTU.TA's Q4 2025 while reporting its net income),
    so no four consecutive quarters exist and every TTM window is skipped. For each annual
    point with no quarterly point at its date, this derives that quarter *only* when exactly
    three plainly consecutive quarters precede it within the year — with two unknowns the
    annual total cannot be split, so it refuses rather than guess. Currency/scale mismatches,
    missing annual data, and non-finite results are also refusals, never fabricated values.

    Exact for additive metrics; approximate for per-share ones (EPS), because the share count
    drifts across the year — callers should disclose that. Returns the new series (date-
    ordered, real points untouched) and the dates it filled.
    """
    if not quarterly.available or not annual.available:
        return quarterly, []

    points = sorted(quarterly.points, key=lambda p: p.date)
    low, high = _QUARTER_SPACING_DAYS
    added: list[Point] = []
    for year_total in sorted(annual.points, key=lambda p: p.date):
        year_end = year_total.date
        if any(abs((p.date - year_end).days) <= _SAME_PERIOD_DAYS for p in points):
            continue
        prior = [
            p
            for p in points
            if 0 < (year_end - p.date).days <= _MAX_QUARTER_WINDOW_DAYS
        ]
        if len(prior) != 3:
            continue
        chain = [*(p.date for p in prior), year_end]
        if not all(low <= (b - a).days <= high for a, b in zip(chain, chain[1:])):
            continue
        try:
            value = year_total.value - reduce(add, (p.value for p in prior))
        except (TypeError, ValueError, AttributeError):
            continue
        if not _is_real(value):
            continue
        added.append(Point(date=year_end, value=value))

    if not added:
        return quarterly, []
    merged = sorted([*points, *added], key=lambda p: p.date)
    return (
        MetricSeries(metric_id=quarterly.metric_id, points=merged, available=True),
        [p.date for p in added],
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


def _money_tags(series: MetricSeries) -> set[tuple[object, object]]:
    return {
        (p.value.currency, p.value.scale)
        for p in series.points
        if isinstance(p.value, Money)
    }


def _with_annual_year_ends(
    ttm: MetricSeries, annual: MetricSeries, quarterly: MetricSeries
) -> tuple[MetricSeries, list[date]]:
    """Add the annual figure as the TTM value at each fiscal year end it has no real point for.

    TTM at a fiscal year end *is* the annual total, so these are exact, not estimates; they
    extend the history past what a source's few quarters allow (Twelve Data's plan returns
    ~6), at yearly cadence. An existing real point near that date always wins — adding a second
    value for one date would make the line jump — while a NaN gap marker there is superseded by
    the real annual value. Annual points whose currency/scale differ from the *quarterly*
    series' are never merged (checked against `quarterly`, not `ttm`, which can be empty when
    every window is a gap — an empty series would accept anything). Returns the series and the
    dates added.
    """
    if not annual.available:
        return ttm, []
    annual_tags, quarterly_tags = _money_tags(annual), _money_tags(quarterly)
    if annual_tags and quarterly_tags and annual_tags != quarterly_tags:
        return ttm, []
    real = [p for p in ttm.points if _is_real(p.value)]
    added = [
        a
        for a in annual.points
        if _is_real(a.value)
        and not any(abs((p.date - a.date).days) <= _SAME_PERIOD_DAYS for p in real)
    ]
    if not added:
        return ttm, []
    kept = [
        p
        for p in ttm.points
        if _is_real(p.value)
        or not any(abs((p.date - a.date).days) <= _SAME_PERIOD_DAYS for a in added)
    ]
    try:
        merged = MetricSeries(
            metric_id=ttm.metric_id,
            points=sorted([*kept, *added], key=lambda p: p.date),
            available=True,
        )
    except ValueError:
        return ttm, []
    return merged, [a.date for a in added]


def _yearly_note(added: dict[str, list[date]]) -> str:
    """One line for every metric that got annual points, not one per metric (a TTM fetch has
    about nine flow metrics and the limits panel would be mostly this)."""
    every = [d for dates in added.values() for d in dates]
    return (
        f"TTM history from {min(every).isoformat()} to {max(every).isoformat()} is yearly "
        "(fiscal-year-end values from the annual statements), not rolling quarterly sums, "
        f"for: {', '.join(added)}"
    )


def _has_ttm_gap(quarterly: MetricSeries, ttm: MetricSeries) -> bool:
    """Whether a flow metric's TTM is missing windows a reconstructed quarter could fix: a
    NaN gap marker, or no TTM at all despite at least four quarters being present."""
    if any(not _is_real(p.value) for p in ttm.points):
        return True
    return not ttm.available and len(quarterly.points) >= 4


def _unfilled_note(metric_id: str) -> str:
    return (
        f"{metric_id}: a quarter is missing at the source and could not be reconstructed "
        "because the annual data was unavailable, so its TTM has gaps"
    )


def _fill_note(metric_id: str, dates: list[date]) -> str:
    shown = ", ".join(d.isoformat() for d in dates)
    return (
        f"{metric_id}: the {shown} quarter is missing at the source and was derived as the "
        "fiscal-year total minus the other three quarters (approximate for per-share metrics)"
    )


def derive_ttm_fundamentals(
    quarterly: CompanyFundamentals,
    annual_loader: Callable[[], CompanyFundamentals | None] | None = None,
) -> CompanyFundamentals:
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

    `annual_loader` (optional) supplies the matching `Period.ANNUAL` fundamentals, used for
    two things: reconstructing a quarter the source omitted (`fill_missing_fourth_quarters`),
    and extending the history with the annual figure as the TTM value at each earlier fiscal
    year end (`_with_annual_year_ends`) — sources return only a few quarters, but TTM at a
    fiscal year end *is* the annual total. It is called **at most once**, but now on every
    call that supplies it, so each TTM fetch costs one extra annual fetch (Twelve Data bills
    the statement endpoints heavily). Returning `None` (e.g. that fetch failed) leaves the
    quarterly-only TTM, with a note if a gap could not be filled. Every reconstruction and the
    yearly cadence of the older history are disclosed in `source_limits`.
    """
    if quarterly.period != Period.QUARTERLY:
        raise ValueError(
            "derive_ttm_fundamentals requires Period.QUARTERLY input, got "
            f"{quarterly.period.value}"
        )

    new_series: dict[str, MetricSeries] = {}
    fill_notes: list[str] = []
    yearly_added: dict[str, list[date]] = {}
    annual: CompanyFundamentals | None = None
    annual_loaded = False
    for metric_id, series in quarterly.series.items():
        if metric_id in _FLOW_METRIC_IDS:
            ttm = ttm_series(series, Period.QUARTERLY, mark_gaps=True)
            if annual_loader is not None:
                if not annual_loaded:
                    annual, annual_loaded = annual_loader(), True
                annual_series = annual.series.get(metric_id) if annual else None
                if _has_ttm_gap(series, ttm):
                    if annual is None:
                        fill_notes.append(_unfilled_note(metric_id))
                    elif annual_series is not None:
                        filled, dates = fill_missing_fourth_quarters(
                            series, annual_series
                        )
                        if dates:
                            ttm = ttm_series(filled, Period.QUARTERLY, mark_gaps=True)
                            fill_notes.append(_fill_note(metric_id, dates))
                if annual_series is not None:
                    ttm, added = _with_annual_year_ends(ttm, annual_series, series)
                    if added:
                        yearly_added[metric_id] = added
            new_series[metric_id] = ttm
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

    source_limits = [*quarterly.source_limits, *fill_notes]
    if yearly_added:
        source_limits.append(_yearly_note(yearly_added))
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

# Optional daily float series: price-currency units per one statement-currency unit
# (USD->ILS ~ 3.2). Not an adapter output — `sources/fx_rate`'s `attach_fx_series` adds
# it after load, only when `eps` and `price` are in different currencies.
FX_RATE_METRIC_ID = "fx_rate"


def _pe_converted(price: Money, eps_ttm: Money, fx_rate: float) -> float:
    return _pe(
        price,
        Money(
            value=eps_ttm.as_base_units() * fx_rate,
            currency=price.currency,
            scale=Unit.ONES,
        ),
    )


PE_RATIO_TTM_FX = TrailingMetric(
    metric_id="pe_ratio_ttm",
    title="P/E (TTM)",
    driver="price",
    inputs=(TrailingInput("eps", ttm=True), TrailingInput(FX_RATE_METRIC_ID)),
    compute=_pe_converted,
)


def pe_ratio_metric(fundamentals: CompanyFundamentals) -> TrailingMetric:
    """The P/E metric to resolve: the FX-converting variant when an `fx_rate` series was
    attached (EPS and price in different currencies), else the plain one. Both renderers
    (matplotlib and web) go through this so they cannot disagree."""
    return PE_RATIO_TTM_FX if FX_RATE_METRIC_ID in fundamentals.series else PE_RATIO_TTM


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
