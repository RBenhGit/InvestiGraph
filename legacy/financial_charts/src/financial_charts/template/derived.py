from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Callable

from financial_charts.template.models import (
    CompanyFundamentals,
    Money,
    MetricSeries,
    Point,
)


@dataclass(frozen=True)
class DerivedMetric:
    """A metric computed from other declared metrics — never supplied by a source.

    Available iff every metric in `inputs` is available on the fundamentals it's
    resolved against; points are computed only for dates common to all inputs.
    """

    metric_id: str
    title: str
    inputs: tuple[str, ...]
    compute: Callable[..., float]


def resolve(fundamentals: CompanyFundamentals, derived: DerivedMetric) -> MetricSeries:
    """Compute `derived`'s series from the base metrics already on `fundamentals`.

    Availability resolves through the inputs: if any required input metric is
    missing or unavailable, the whole derived series is unavailable — a source's
    declared gap propagates to every quantity computed from it, so a chart can
    gate on `derived.inputs` exactly like it gates on a normal metric.
    """
    input_series = [fundamentals.series.get(metric_id) for metric_id in derived.inputs]
    if not input_series or any(
        series is None or not series.available for series in input_series
    ):
        return MetricSeries(metric_id=derived.metric_id, available=False)

    values_by_date: list[dict[date, Money | float]] = [
        {point.date: point.value for point in series.points} for series in input_series
    ]
    common_dates = sorted(set.intersection(*(set(d) for d in values_by_date)))

    points: list[Point] = []
    for d in common_dates:
        try:
            value = derived.compute(*(values[d] for values in values_by_date))
        except (ZeroDivisionError, ValueError, AttributeError, TypeError):
            # A single bad point (division by zero, a currency mismatch a
            # `compute` fn didn't expect, an unexpected value shape) degrades to
            # a skipped point, never a crash — if every point fails this way the
            # series ends up empty and callers see `available=False`, same as
            # any other gap.
            continue
        points.append(Point(date=d, value=value))

    return MetricSeries(
        metric_id=derived.metric_id, points=points, available=bool(points)
    )


def ratio(numerator: Money, denominator: Money) -> float:
    """A dimensionless ratio between two same-currency `Money` values.

    Compares amounts via `as_base_units()` so the two operands' scales cancel
    correctly — dividing raw `.value`s would silently misprice a metric declared
    in millions against one declared in ones, the same trap `Money` exists to
    prevent for addition.
    """
    numerator.require_same_currency(denominator)
    return numerator.as_base_units() / denominator.as_base_units()


FCF_MARGIN = DerivedMetric(
    metric_id="fcf_margin",
    title="FCF Margin",
    inputs=("free_cash_flow", "revenue"),
    compute=ratio,
)

CURRENT_RATIO = DerivedMetric(
    metric_id="current_ratio",
    title="Current Ratio",
    inputs=("total_current_assets", "total_current_liabilities"),
    compute=ratio,
)

DEBT_TO_EQUITY = DerivedMetric(
    metric_id="debt_to_equity",
    title="Debt / Equity",
    inputs=("total_debt", "total_equity"),
    compute=ratio,
)


def _roce(ebit: Money, total_assets: Money, total_current_liabilities: Money) -> float:
    """Return on Capital Employed: EBIT / (Total Assets - Current Liabilities)."""
    capital_employed = total_assets - total_current_liabilities
    return ratio(ebit, capital_employed)


def _roic(
    net_income: Money, total_debt: Money, total_equity: Money, cash: Money
) -> float:
    """Return on Invested Capital, approximated with Net Income (an after-tax
    figure) over Invested Capital (Debt + Equity - Cash) — a simplification of
    the textbook NOPAT/Invested Capital formula that avoids needing a
    separately-fetched effective tax rate.
    """
    invested_capital = (total_debt + total_equity) - cash
    return ratio(net_income, invested_capital)


ROCE = DerivedMetric(
    metric_id="roce",
    title="ROCE",
    inputs=("ebit", "total_assets", "total_current_liabilities"),
    compute=_roce,
)

ROIC = DerivedMetric(
    metric_id="roic",
    title="ROIC",
    inputs=("net_income", "total_debt", "total_equity", "cash_and_equivalents"),
    compute=_roic,
)


def _book_value_per_share(total_equity: Money, shares_outstanding: float) -> float:
    return total_equity.as_base_units() / shares_outstanding


BOOK_VALUE_PER_SHARE = DerivedMetric(
    metric_id="book_value_per_share",
    title="Book Value / Share",
    inputs=("total_equity", "shares_outstanding"),
    compute=_book_value_per_share,
)
